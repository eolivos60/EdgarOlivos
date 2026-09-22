#!/usr/bin/env pwsh
<#!
.SYNOPSIS
    Update dash_auth value inside MERAKI_COOKIES in .env

.DESCRIPTION
    Updates the dash_auth cookie in MERAKI_COOKIES. If .env is missing,
    it creates one with MERAKI_COOKIES=dash_auth=<value>.

.EXAMPLE
    .\update_dash_auth.ps1 -DashAuth "MG..."
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$DashAuth
)

$envFile = Join-Path $PSScriptRoot ".env"

if ([string]::IsNullOrWhiteSpace($DashAuth)) {
    Write-Host "ERROR: DashAuth cannot be empty." -ForegroundColor Red
    exit 1
}

Write-Host "NOTE: Meraki /api/v1 endpoints are officially API-key based. dash_auth cookie auth may fail with HTTP 401." -ForegroundColor Yellow

if (-not (Test-Path $envFile)) {
    "MERAKI_COOKIES=dash_auth=$DashAuth" | Set-Content -Path $envFile -NoNewline
    Write-Host "Created .env and set MERAKI_COOKIES with dash_auth." -ForegroundColor Green
    Write-Host "Next step: run reload_credentials in your approved MCP client." -ForegroundColor Cyan
    exit 0
}

$content = Get-Content $envFile -Raw

if ($content -match '(?m)^\s*MERAKI_COOKIES=(.*)$') {
    $currentCookies = $Matches[1]

    if ($currentCookies -match '(^|;)\s*dash_auth=([^;]*)') {
        $oldDashAuth = $Matches[2]
        $newCookies = $currentCookies -replace [regex]::Escape("dash_auth=$oldDashAuth"), "dash_auth=$DashAuth"
    } else {
        if ([string]::IsNullOrWhiteSpace($currentCookies)) {
            $newCookies = "dash_auth=$DashAuth"
        } else {
            $trimmed = $currentCookies.TrimEnd()
            if ($trimmed.EndsWith(';')) {
                $newCookies = "$trimmed dash_auth=$DashAuth"
            } else {
                $newCookies = "$trimmed; dash_auth=$DashAuth"
            }
        }
    }

    $newContent = [regex]::Replace(
        $content,
        '(?m)^\s*MERAKI_COOKIES=.*$',
        "MERAKI_COOKIES=$newCookies",
        1
    )

    Set-Content -Path $envFile -Value $newContent -NoNewline
    Write-Host "Updated dash_auth in MERAKI_COOKIES." -ForegroundColor Green
    Write-Host "Next step: run reload_credentials in your approved MCP client." -ForegroundColor Cyan
    exit 0
}

# MERAKI_COOKIES not present, append it
$append = "`r`nMERAKI_COOKIES=dash_auth=$DashAuth"
Set-Content -Path $envFile -Value ($content + $append) -NoNewline
Write-Host "Added MERAKI_COOKIES with dash_auth to .env." -ForegroundColor Green
Write-Host "Next step: run reload_credentials in your approved MCP client." -ForegroundColor Cyan
exit 0
