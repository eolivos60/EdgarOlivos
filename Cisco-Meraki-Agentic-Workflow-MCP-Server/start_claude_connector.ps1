param(
    [string]$PublicMcpUrl = "",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 3000,
    [string]$McpPath = "/mcp",
    [switch]$NoTunnel,
    [switch]$Stop,
    [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$serverScript = Join-Path $repoRoot "server.py"
$preflightScript = Join-Path $repoRoot "validate_claude_connector.ps1"
$logDir = Join-Path $repoRoot "logs"
$mcpLog = Join-Path $logDir "mcp_http.log"
$mcpErrLog = Join-Path $logDir "mcp_http.err.log"
$cloudflaredLog = Join-Path $logDir "cloudflared.log"
$cloudflaredErrLog = Join-Path $logDir "cloudflared.err.log"
$mcpPidFile = Join-Path $repoRoot ".mcp_server.pid"
$cloudflaredPidFile = Join-Path $repoRoot ".cloudflared.pid"
$cloudflaredUrlFile = Join-Path $repoRoot ".cloudflared.url"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

function Resolve-CloudflaredPath {
    $candidates = @(
        "$env:ProgramFiles\cloudflared\cloudflared.exe",
        "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe"
    )

    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        $candidates += $cmd.Source
    }

    foreach ($path in $candidates) {
        if (Test-Path $path) {
            try {
                $null = & $path --version
                return $path
            }
            catch {
                continue
            }
        }
    }

    throw "cloudflared.exe not found. Install Cloudflare cloudflared first."
}

function Get-TryCloudflareBaseUrl {
    param([string[]]$LogPaths)

    $regex = [regex]"https://[a-z0-9-]+\.trycloudflare\.com"
    foreach ($path in $LogPaths) {
        if (-not (Test-Path $path)) { continue }
        # Use FileShare.ReadWrite so we can read a file that cloudflared
        # holds open for writing (Start-Process redirect holds an exclusive
        # write handle; Get-Content -Raw silently returns $null in that case).
        $content = $null
        try {
            $stream = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            try {
                $reader = [System.IO.StreamReader]::new($stream)
                $content = $reader.ReadToEnd()
            }
            finally {
                $reader.Dispose()
                $stream.Dispose()
            }
        }
        catch {
            continue
        }
        if (-not $content) { continue }
        $match = $regex.Match($content)
        if ($match.Success) {
            return $match.Value
        }
    }

    return $null
}

function Resolve-McpAuthToken {
    $token = ($env:MCP_AUTH_TOKEN | Out-String).Trim()
    if ($token) {
        return $token
    }

    $envFile = Join-Path $repoRoot ".env"
    if (-not (Test-Path $envFile)) {
        return ""
    }

    $line = Get-Content $envFile -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*MCP_AUTH_TOKEN\s*=' } |
        Select-Object -First 1

    if (-not $line) {
        return ""
    }

    $value = ($line -split '=', 2)[1].Trim()
    if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    elseif ($value.StartsWith("'") -and $value.EndsWith("'") -and $value.Length -ge 2) {
        $value = $value.Substring(1, $value.Length - 2)
    }

    return $value
}

$mcpAuthToken = Resolve-McpAuthToken

function Get-JsonRpcInitializePayload {
    return (@{
            jsonrpc = "2.0"
            id = 1
            method = "initialize"
            params = @{
                protocolVersion = "2025-03-26"
                capabilities = @{}
                clientInfo = @{
                    name = "launcher-check"
                    version = "1.0"
                }
            }
        } | ConvertTo-Json -Depth 8)
}

function Test-McpInitialize {
    param([string]$Url)

    try {
        $headers = @{ Accept = "application/json, text/event-stream" }
        if ($mcpAuthToken) {
            $headers["Authorization"] = "Bearer $mcpAuthToken"
        }

        $requestParams = @{
            Uri = $Url
            Method = "Post"
            ContentType = "application/json"
            Headers = $headers
            Body = (Get-JsonRpcInitializePayload)
            UseBasicParsing = $true
            TimeoutSec = 10
        }
        $resp = Invoke-WebRequest @requestParams

        return ($resp.StatusCode -eq 200) -and ($resp.Content -match '"result"')
    }
    catch {
        return $false
    }
}

function Read-Pid {
    param([string]$Path)

    if (Test-Path $Path) {
        $raw = Get-Content $Path -ErrorAction SilentlyContinue | Select-Object -First 1
        $pidValue = 0
        if ([int]::TryParse($raw, [ref]$pidValue)) {
            return $pidValue
        }
    }

    return $null
}

function Stop-PidIfRunning {
    param(
        [string]$Name,
        [string]$PidFile
    )

    $pidValue = Read-Pid -Path $PidFile
    if (-not $pidValue) {
        Write-Host "[INFO] No PID file for $Name"
        return
    }

    $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $pidValue -Force
        Write-Host "[STOPPED] $Name (PID $pidValue)"
    }
    else {
        Write-Host "[INFO] $Name PID not running (PID $pidValue)"
    }

    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

if ($Stop) {
    Stop-PidIfRunning -Name "cloudflared" -PidFile $cloudflaredPidFile
    Stop-PidIfRunning -Name "mcp-server" -PidFile $mcpPidFile
    Remove-Item $cloudflaredUrlFile -Force -ErrorAction SilentlyContinue
    Write-Host "Done."
    exit 0
}

if (-not (Test-Path $pythonExe)) {
    throw "Python venv executable not found: $pythonExe"
}

if (-not (Test-Path $serverScript)) {
    throw "server.py not found: $serverScript"
}

$cloudflaredExe = $null
if (-not $NoTunnel) {
    $cloudflaredExe = Resolve-CloudflaredPath
}
$localUrl = "http://${BindHost}:$Port$McpPath"

if ($PublicMcpUrl) {
    $publicUrl = $PublicMcpUrl
}
elseif (Test-Path $cloudflaredUrlFile) {
    $savedBaseUrl = (Get-Content $cloudflaredUrlFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($savedBaseUrl) {
        $publicUrl = "$savedBaseUrl$McpPath"
    }
}
else {
    $publicUrl = ""
}

Write-Host "=== MCP Connector Launcher ===" -ForegroundColor Cyan
Write-Host "Local MCP : $localUrl"
if ($publicUrl) {
    Write-Host "Public MCP: $publicUrl"
}
else {
    if ($NoTunnel) {
        Write-Host "Public MCP: (not managed by this script; pass -PublicMcpUrl if available)"
    }
    else {
        Write-Host "Public MCP: (will be discovered from cloudflared quick tunnel)"
    }
}

$localReady = Test-McpInitialize -Url $localUrl
if ($localReady) {
    Write-Host "[OK] Local MCP endpoint already responding."
}
else {
    Write-Host "[START] Launching MCP HTTP server..."
    $mcpArgs = @(
        "`"$serverScript`"",
        "--transport", "http",
        "--host", $BindHost,
        "--port", "$Port",
        "--path", $McpPath
    )

    $mcpStartParams = @{
        FilePath = $pythonExe
        ArgumentList = $mcpArgs
        WorkingDirectory = $repoRoot
        RedirectStandardOutput = $mcpLog
        RedirectStandardError = $mcpErrLog
        PassThru = $true
    }
    $mcpProc = Start-Process @mcpStartParams

    Set-Content -Path $mcpPidFile -Value $mcpProc.Id
    $becameReady = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        if (Test-McpInitialize -Url $localUrl) {
            $becameReady = $true
            break
        }
    }

    if (-not $becameReady) {
        Write-Host "[FAIL] Local MCP endpoint did not come online. Check: $mcpLog" -ForegroundColor Red
        exit 1
    }

    Write-Host "[OK] MCP server started (PID $($mcpProc.Id))."
}

if ($NoTunnel) {
    Write-Host "[SKIP] Tunnel startup skipped (-NoTunnel)."
}
else {
    $cloudflaredHealthy = $false
    $cloudflaredPid = Read-Pid -Path $cloudflaredPidFile
    if ($cloudflaredPid) {
        $cloudflaredProc = Get-Process -Id $cloudflaredPid -ErrorAction SilentlyContinue
        if ($cloudflaredProc) {
            $candidateBaseUrl = $null
            if ($PublicMcpUrl) {
                $candidateBaseUrl = $PublicMcpUrl -replace [regex]::Escape($McpPath) + '$', ''
            }
            elseif (Test-Path $cloudflaredUrlFile) {
                $candidateBaseUrl = (Get-Content $cloudflaredUrlFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
            }

            if ($candidateBaseUrl) {
                $candidatePublicUrl = "$candidateBaseUrl$McpPath"
                if (Test-McpInitialize -Url $candidatePublicUrl) {
                    $cloudflaredHealthy = $true
                    $publicUrl = $candidatePublicUrl
                }
            }
        }
    }

    if ($cloudflaredHealthy) {
        Write-Host "[OK] cloudflared quick tunnel already healthy."
    }
    else {
        Write-Host "[START] Launching cloudflared quick tunnel..."

        $cloudflaredArgs = @(
            "tunnel",
            "--url", "http://${BindHost}:$Port",
            "--protocol", "http2"
        )

        $cloudflaredStartParams = @{
            FilePath = $cloudflaredExe
            ArgumentList = $cloudflaredArgs
            WorkingDirectory = $repoRoot
            RedirectStandardOutput = $cloudflaredLog
            RedirectStandardError = $cloudflaredErrLog
            PassThru = $true
        }
        $cloudflaredProc = Start-Process @cloudflaredStartParams

        Set-Content -Path $cloudflaredPidFile -Value $cloudflaredProc.Id

        $discoveredBaseUrl = $null
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1

            if ($cloudflaredProc.HasExited) {
                Write-Host "[FAIL] cloudflared exited early. Check: $cloudflaredErrLog" -ForegroundColor Red
                exit 1
            }

            $discoveredBaseUrl = Get-TryCloudflareBaseUrl -LogPaths @($cloudflaredLog, $cloudflaredErrLog)
            if ($discoveredBaseUrl) {
                break
            }
        }

        if (-not $discoveredBaseUrl) {
            Write-Host "[FAIL] Could not discover quick tunnel URL from cloudflared logs." -ForegroundColor Red
            Write-Host "Logs: $cloudflaredLog and $cloudflaredErrLog"
            exit 1
        }

        Set-Content -Path $cloudflaredUrlFile -Value $discoveredBaseUrl
        $publicUrl = "$discoveredBaseUrl$McpPath"
        Write-Host "[OK] cloudflared started (PID $($cloudflaredProc.Id))."
    }
}

if ((-not $publicUrl) -and (-not $NoTunnel)) {
    Write-Host "[FAIL] Public MCP URL could not be determined." -ForegroundColor Red
    exit 1
}

Write-Host "Public MCP: $publicUrl"

if (-not $SkipPreflight) {
    if (-not (Test-Path $preflightScript)) {
        Write-Host "[WARN] Preflight script not found: $preflightScript"
        exit 1
    }

    Write-Host "[CHECK] Running preflight checks..."
    $preflightArgs = @(
        "-ExecutionPolicy", "Bypass",
        "-File", $preflightScript,
        "-LocalMcpUrl", $localUrl
    )

    if ($publicUrl) {
        $preflightArgs += @("-PublicMcpUrl", $publicUrl)
    }
    if ($NoTunnel) {
        $preflightArgs += "-SkipTunnelProcessCheck"
    }

    & powershell @preflightArgs
    $preflightExitCode = $LASTEXITCODE

    if ($preflightExitCode -ne 0) {
        Write-Host "[FAIL] Preflight failed." -ForegroundColor Red
        Write-Host "Logs: $mcpLog and $cloudflaredLog"
        exit $preflightExitCode
    }
}

Write-Host ""
Write-Host "READY: MCP connector is up." -ForegroundColor Green
if ($publicUrl) {
    Write-Host "Connect URL: $publicUrl"
}
else {
    Write-Host "Connect URL: (managed externally; use your Cisco-provided URL)"
}
Write-Host ""
Write-Host "To stop managed processes:"
Write-Host "powershell -ExecutionPolicy Bypass -File .\start_claude_connector.ps1 -Stop"
exit 0
