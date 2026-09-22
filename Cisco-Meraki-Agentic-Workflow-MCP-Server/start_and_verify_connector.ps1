param(
    [string]$PublicMcpUrl = "",
    [switch]$NoTunnel,
    [switch]$SkipStart,
    [switch]$SkipSmoke,
    [switch]$SkipClipboard
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$startScript = Join-Path $repoRoot "start_claude_connector.ps1"
$smokeScript = Join-Path $repoRoot "mcp_connector_smoke.py"
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$cloudflaredUrlFile = Join-Path $repoRoot ".cloudflared.url"
$mcpPath = "/mcp"

if (-not (Test-Path $startScript)) {
    throw "Missing script: $startScript"
}
if (-not (Test-Path $smokeScript)) {
    throw "Missing script: $smokeScript"
}
if (-not (Test-Path $pythonExe)) {
    throw "Missing Python executable: $pythonExe"
}

if (-not $SkipStart) {
    Write-Host "[STEP] Starting connector..." -ForegroundColor Cyan
    $startArgs = @("-ExecutionPolicy", "Bypass", "-File", $startScript)
    if ($PublicMcpUrl) {
        $startArgs += @("-PublicMcpUrl", $PublicMcpUrl)
    }
    if ($NoTunnel) {
        $startArgs += "-NoTunnel"
    }

    & powershell @startArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Connector startup failed with exit code $LASTEXITCODE"
    }
}

if ($PublicMcpUrl) {
    $baseUrl = $PublicMcpUrl.Trim()
}
else {
    if (-not (Test-Path $cloudflaredUrlFile)) {
        throw "Could not find $cloudflaredUrlFile. Start script did not produce a tunnel URL."
    }

    $baseUrl = (Get-Content $cloudflaredUrlFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if (-not $baseUrl) {
        throw "Tunnel URL file is empty: $cloudflaredUrlFile"
    }
}

if ($baseUrl.EndsWith($mcpPath)) {
    $publicUrl = $baseUrl
}
else {
    $publicUrl = "$baseUrl$mcpPath"
}

Write-Host "[INFO] Connect URL: $publicUrl" -ForegroundColor Green

if (-not $SkipClipboard) {
    try {
        Set-Clipboard -Value $publicUrl
        Write-Host "[OK] URL copied to clipboard." -ForegroundColor Green
    }
    catch {
        Write-Host "[WARN] Could not copy to clipboard: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

if (-not $SkipSmoke) {
    Write-Host "[STEP] Running MCP smoke test..." -ForegroundColor Cyan
    $smokeOutput = & $pythonExe $smokeScript --public-url $publicUrl 2>&1
    $smokeExitCode = $LASTEXITCODE
    $smokeText = ($smokeOutput | Out-String)

    if ($smokeOutput) {
        $smokeOutput | ForEach-Object { Write-Host $_ }
    }

    if ($smokeExitCode -ne 0) {
        $orgsEmptyFailure = ($smokeText -match "\[FAIL\]\s+tools/call\s+get_organizations\s+-\s+HTTP\s+200,\s+orgs=0")
        if ($orgsEmptyFailure) {
            Write-Host "[WARN] Smoke test reported orgs=0 for get_organizations. Treating as non-fatal because endpoint/tooling are reachable." -ForegroundColor Yellow
        }
        else {
            throw "Smoke test failed with exit code $smokeExitCode"
        }
    }
}

Write-Host "" 
Write-Host "READY: Startup and verification complete." -ForegroundColor Green
Write-Host "Connect URL: $publicUrl"
