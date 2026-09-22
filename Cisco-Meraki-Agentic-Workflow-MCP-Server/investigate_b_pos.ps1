$envPath = '.\.env'
$kv = @{}
Get-Content $envPath | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $i = $_.IndexOf('=')
  if ($i -gt 0) { $kv[$_.Substring(0, $i).Trim()] = $_.Substring($i + 1) }
}

$dashboardHost = $kv['MERAKI_DASHBOARD_HOST']
$cookies = $kv['MERAKI_COOKIES']
$csrf = $kv['MERAKI_CSRF_TOKEN']
$referer = $kv['MERAKI_REFERER']
$page = $kv['MERAKI_PAGELOAD_REQUEST_ID']

$networkId = 'L_656399645689271382'
$ssidName = 'B_POS'
$base = "https://$dashboardHost/api/v1"

$headers = @{
  'Accept' = 'application/json'
  'Content-Type' = 'application/json'
  'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
}
if ($csrf) { $headers['x-csrf-token'] = $csrf }
if ($referer) { $headers['referer'] = $referer }
if ($page) { $headers['x-pageload-request-id'] = $page }

$ws = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$cc = New-Object System.Net.CookieContainer
$cookies.Split(';') | ForEach-Object {
  $p = $_.Trim()
  if ($p -and $p.Contains('=')) {
    $n, $v = $p.Split('=', 2)
    $cc.Add((New-Object System.Net.Cookie($n.Trim(), $v.Trim(), '/', $dashboardHost)))
  }
}
$ws.Cookies = $cc

$ssids = Invoke-RestMethod -Method Get -Uri "$base/networks/$networkId/wireless/ssids" -Headers $headers -WebSession $ws -TimeoutSec 40
$target = @($ssids) | Where-Object { $_.name -eq $ssidName } | Select-Object -First 1
if (-not $target) { throw "SSID '$ssidName' not found" }

$clients2h = Invoke-RestMethod -Method Get -Uri "$base/networks/$networkId/clients?timespan=7200&perPage=250" -Headers $headers -WebSession $ws -TimeoutSec 40
$clients24h = Invoke-RestMethod -Method Get -Uri "$base/networks/$networkId/clients?timespan=86400&perPage=250" -Headers $headers -WebSession $ws -TimeoutSec 40
$alerts = Invoke-RestMethod -Method Get -Uri "$base/networks/$networkId/health/alerts" -Headers $headers -WebSession $ws -TimeoutSec 40

$bpos2h = @($clients2h) | Where-Object { ("$($_.ssid)").Trim() -eq $ssidName }
$bpos24h = @($clients24h) | Where-Object { ("$($_.ssid)").Trim() -eq $ssidName }

$apTop2h = $bpos2h | Group-Object recentDeviceName | Sort-Object Count -Descending | Select-Object -First 8 Name, Count
$manTop24h = $bpos24h | Group-Object manufacturer | Sort-Object Count -Descending | Select-Object -First 8 Name, Count

$relatedAlerts = @($alerts) | Where-Object {
  ("$($_.type)" -match 'uplink|Unreachable|wireless|association|authentication|DHCP') -or
  ("$($_.scope.devices.name)" -match 'CloakRm|B_POS')
}

$result = [pscustomobject]@{
  timestamp = (Get-Date).ToString('o')
  networkId = $networkId
  ssid = [pscustomobject]@{
    number = $target.number
    name = $target.name
    enabled = $target.enabled
    authMode = $target.authMode
    encryptionMode = $target.encryptionMode
    ipAssignmentMode = $target.ipAssignmentMode
    lanIsolationEnabled = $target.lanIsolationEnabled
    minBitrate = $target.minBitrate
    bandSelection = $target.bandSelection
    mandatoryDhcpEnabled = $target.mandatoryDhcpEnabled
  }
  clientCounts = [pscustomobject]@{
    bpos_2h = @($bpos2h).Count
    bpos_24h = @($bpos24h).Count
  }
  topApsForBpos2h = @($apTop2h)
  topManufacturersBpos24h = @($manTop24h)
  sampleBposClients2h = @($bpos2h | Select-Object -First 12 description, mac, ip, manufacturer, recentDeviceName, recentDeviceSerial, status, ssid)
  relatedAlerts = @($relatedAlerts | Select-Object -First 8 id, category, type, severity, scope)
}

$result | ConvertTo-Json -Depth 8
