param(
    [string]$PublicMcpUrl = "",
    [string]$LocalMcpUrl = "http://127.0.0.1:3000/mcp",
    [string]$CloudflaredPidFile = ".cloudflared.pid",
    [string]$CloudflaredUrlFile = ".cloudflared.url",
    [string]$TunnelProcessName = "cloudflared",
    [switch]$SkipTunnelProcessCheck,
    [int]$TimeoutSec = 15
)

$ErrorActionPreference = "Stop"
$allPassed = $true
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $PublicMcpUrl) {
    $urlFilePath = if ([System.IO.Path]::IsPathRooted($CloudflaredUrlFile)) {
        $CloudflaredUrlFile
    }
    else {
        Join-Path $repoRoot $CloudflaredUrlFile
    }

    if (Test-Path $urlFilePath) {
        $savedBaseUrl = (Get-Content $urlFilePath -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
        if ($savedBaseUrl) {
            $mcpPath = "/mcp"
            try {
                $localUri = [Uri]$LocalMcpUrl
                if ($localUri.AbsolutePath) {
                    $mcpPath = $localUri.AbsolutePath
                }
            }
            catch {
                $mcpPath = "/mcp"
            }

            if ($savedBaseUrl.EndsWith("/")) {
                $savedBaseUrl = $savedBaseUrl.TrimEnd("/")
            }
            $PublicMcpUrl = "$savedBaseUrl$mcpPath"
        }
    }
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

function Write-Check {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Detail
    )

    if ($Passed) {
        Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red
    }
}

function Invoke-McpInitialize {
    param(
        [string]$Url,
        [int]$Id = 1
    )

    $payload = @{
        jsonrpc = "2.0"
        id = $Id
        method = "initialize"
        params = @{
            protocolVersion = "2025-03-26"
            capabilities = @{}
            clientInfo = @{
                name = "mcp-preflight"
                version = "1.0"
            }
        }
    } | ConvertTo-Json -Depth 8

    $headers = @{ Accept = "application/json, text/event-stream" }
    if ($mcpAuthToken) {
        $headers["Authorization"] = "Bearer $mcpAuthToken"
    }

    return Invoke-WebRequest `
        -Uri $Url `
        -Method Post `
        -ContentType "application/json" `
        -Headers $headers `
        -Body $payload `
        -UseBasicParsing `
        -TimeoutSec $TimeoutSec
}

Write-Host "=== MCP Preflight ===" -ForegroundColor Cyan
Write-Host "Public URL: $PublicMcpUrl"
Write-Host "Local URL : $LocalMcpUrl"
Write-Host ""

# 1) Local TCP port check
$localTcpOk = $false
try {
    $tcp = Test-NetConnection -ComputerName "127.0.0.1" -Port 3000 -WarningAction SilentlyContinue
    $localTcpOk = [bool]$tcp.TcpTestSucceeded
    Write-Check -Name "Local TCP 127.0.0.1:3000" -Passed $localTcpOk -Detail ("TcpTestSucceeded={0}" -f $localTcpOk)
}
catch {
    Write-Check -Name "Local TCP 127.0.0.1:3000" -Passed $false -Detail $_.Exception.Message
}
if (-not $localTcpOk) { $allPassed = $false }

# 2) Local MCP initialize
$localInitOk = $false
try {
    $localResp = Invoke-McpInitialize -Url $LocalMcpUrl -Id 100
    $localInitOk = ($localResp.StatusCode -eq 200) -and ($localResp.Content -match '"result"')
    Write-Check -Name "Local MCP initialize" -Passed $localInitOk -Detail ("HTTP {0}" -f $localResp.StatusCode)
}
catch {
    Write-Check -Name "Local MCP initialize" -Passed $false -Detail $_.Exception.Message
}
if (-not $localInitOk) { $allPassed = $false }

# 3) Tunnel process health (optional for externally managed providers)
$tunnelCheckName = "$TunnelProcessName process"
if ($SkipTunnelProcessCheck) {
    Write-Check -Name $tunnelCheckName -Passed $true -Detail "skipped"
}
else {
    $tunnelOk = $false
    try {
        $pidValue = 0
        if (Test-Path $CloudflaredPidFile) {
            $rawPid = Get-Content $CloudflaredPidFile -ErrorAction SilentlyContinue | Select-Object -First 1
            $null = [int]::TryParse($rawPid, [ref]$pidValue)
        }

        if ($pidValue -gt 0) {
            $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
            if ($proc) {
                $tunnelOk = $true
                Write-Check -Name $tunnelCheckName -Passed $true -Detail ("pid={0}" -f $pidValue)
            }
            else {
                $procCount = @(Get-Process -Name $TunnelProcessName -ErrorAction SilentlyContinue).Count
                $tunnelOk = $procCount -gt 0
                Write-Check -Name $tunnelCheckName -Passed $tunnelOk -Detail ("stale pid={0}; count={1}" -f $pidValue, $procCount)
            }
        }
        else {
            $procCount = @(Get-Process -Name $TunnelProcessName -ErrorAction SilentlyContinue).Count
            $tunnelOk = $procCount -gt 0
            Write-Check -Name $tunnelCheckName -Passed $tunnelOk -Detail ("count={0}" -f $procCount)
        }
    }
    catch {
        Write-Check -Name $tunnelCheckName -Passed $false -Detail $_.Exception.Message
    }
    if (-not $tunnelOk) { $allPassed = $false }
}

# 4) Public MCP initialize
$publicInitOk = $false
if (-not $PublicMcpUrl) {
    Write-Check -Name "Public MCP initialize" -Passed $false -Detail "PublicMcpUrl is empty"
}
else {
    try {
        $publicResp = Invoke-McpInitialize -Url $PublicMcpUrl -Id 200
        $publicInitOk = ($publicResp.StatusCode -eq 200) -and ($publicResp.Content -match '"result"')
        Write-Check -Name "Public MCP initialize" -Passed $publicInitOk -Detail ("HTTP {0}" -f $publicResp.StatusCode)
    }
    catch {
        $detail = $_.Exception.Message
        if ($_.Exception.Response) {
            try {
                $status = [int]$_.Exception.Response.StatusCode
                $detail = "HTTP $status"
            }
            catch {
                $detail = $_.Exception.Message
            }
        }
        Write-Check -Name "Public MCP initialize" -Passed $false -Detail $detail
    }
}
if (-not $publicInitOk) { $allPassed = $false }

Write-Host ""
if ($allPassed) {
    Write-Host "READY: MCP connector preflight passed." -ForegroundColor Green
    exit 0
}
else {
    Write-Host "NOT READY: One or more checks failed." -ForegroundColor Red
    Write-Host "Tip: verify VPN/proxy, tunnel/public URL, and local server process." -ForegroundColor Yellow
    exit 1
}
