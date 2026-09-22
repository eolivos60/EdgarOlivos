#!/usr/bin/env pwsh
<#!
.SYNOPSIS
    Extract .env credentials from a Meraki browser curl command.

.DESCRIPTION
    Parses curl text copied from browser dev tools and extracts:
      - MERAKI_DASHBOARD_HOST
      - MERAKI_COOKIES
      - MERAKI_CSRF_TOKEN
      - MERAKI_REFERER
      - MERAKI_PAGELOAD_REQUEST_ID

    By default, prints an .env snippet to stdout.
    Use -WriteEnv to update/create .env at -EnvPath.

.EXAMPLES
    # 1) Paste command directly
    .\extract_env_from_curl.ps1 -CurlText "curl 'https://n98.dashboard.meraki.com/..." 

    # 2) Read from file
    .\extract_env_from_curl.ps1 -InputFile .\captured_curl.txt

    # 3) Read from clipboard and write to .env
    .\extract_env_from_curl.ps1 -FromClipboard -WriteEnv
#>

[CmdletBinding()]
param(
    [string]$CurlText,
    [string]$InputFile,
    [switch]$FromClipboard,
    [switch]$WriteEnv,
    [string]$EnvPath = (Join-Path $PSScriptRoot ".env")
)

function Get-RegexValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [Parameter(Mandatory = $true)]
        [string]$Pattern,
        [int]$GroupIndex = 1
    )

    $m = [regex]::Match($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($m.Success) {
        return $m.Groups[$GroupIndex].Value.Trim()
    }
    return $null
}

function Set-Or-AddEnvLine {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$Lines,
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Value
    )

    $pattern = "^\s*$([regex]::Escape($Key))="
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match $pattern) {
            $Lines[$i] = "$Key=$Value"
            return
        }
    }

    $Lines.Add("$Key=$Value") | Out-Null
}

# Input source priority: -CurlText > -InputFile > -FromClipboard > clipboard fallback
if (-not [string]::IsNullOrWhiteSpace($CurlText)) {
    $raw = $CurlText
} elseif (-not [string]::IsNullOrWhiteSpace($InputFile)) {
    if (-not (Test-Path $InputFile)) {
        Write-Error "Input file not found: $InputFile"
        exit 1
    }
    $raw = Get-Content -Path $InputFile -Raw
} else {
    $useClipboard = $FromClipboard.IsPresent -or [string]::IsNullOrWhiteSpace($CurlText)
    if ($useClipboard) {
        try {
            $raw = Get-Clipboard -Raw
        } catch {
            Write-Error "Failed to read clipboard. Provide -CurlText or -InputFile."
            exit 1
        }
    }
}

if ([string]::IsNullOrWhiteSpace($raw)) {
    Write-Error "No curl input found. Provide -CurlText, -InputFile, or copy command to clipboard."
    exit 1
}

$url = Get-RegexValue -Text $raw -Pattern 'curl\s+["''](https?://[^"''\s]+)["'']'
if (-not $url) {
    Write-Error "Could not find curl URL."
    exit 1
}

try {
    $uri = [uri]$url
    $dashboardHost = $uri.Host
} catch {
    Write-Error "Invalid URL extracted from curl input: $url"
    exit 1
}

$cookies = Get-RegexValue -Text $raw -Pattern '-b\s+["'']([^"'']+)["'']'
$csrf = Get-RegexValue -Text $raw -Pattern '-H\s+["'']x-csrf-token:\s*([^"'']+)["'']'
$referer = Get-RegexValue -Text $raw -Pattern '-H\s+["'']referer:\s*([^"'']+)["'']'
$pageloadId = Get-RegexValue -Text $raw -Pattern '-H\s+["'']x-pageload-request-id:\s*([^"'']+)["'']'

if (-not $cookies) {
    Write-Warning "MERAKI_COOKIES not found (-b ...)."
}
if (-not $csrf) {
    Write-Warning "MERAKI_CSRF_TOKEN not found (x-csrf-token header)."
}
if (-not $referer) {
    Write-Warning "MERAKI_REFERER not found (referer header)."
}
if (-not $pageloadId) {
    Write-Warning "MERAKI_PAGELOAD_REQUEST_ID not found (x-pageload-request-id header)."
}

$values = [ordered]@{
    MERAKI_DASHBOARD_HOST = $dashboardHost
    MERAKI_COOKIES = $(if ($null -ne $cookies) { $cookies } else { "" })
    MERAKI_CSRF_TOKEN = $(if ($null -ne $csrf) { $csrf } else { "" })
    MERAKI_REFERER = $(if ($null -ne $referer) { $referer } else { "" })
    MERAKI_PAGELOAD_REQUEST_ID = $(if ($null -ne $pageloadId) { $pageloadId } else { "" })
}

Write-Host "Extracted .env values:" -ForegroundColor Cyan
$snippet = ($values.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "`n"
Write-Output $snippet

if ($WriteEnv) {
    $lines = New-Object 'System.Collections.Generic.List[string]'
    if (Test-Path $EnvPath) {
        (Get-Content -Path $EnvPath) | ForEach-Object { $lines.Add($_) | Out-Null }
    }

    foreach ($kv in $values.GetEnumerator()) {
        Set-Or-AddEnvLine -Lines $lines -Key $kv.Key -Value $kv.Value
    }

    Set-Content -Path $EnvPath -Value $lines
    Write-Host "Updated env file: $EnvPath" -ForegroundColor Green
    Write-Host "Next step: run reload_credentials in your approved MCP client." -ForegroundColor Cyan
}
