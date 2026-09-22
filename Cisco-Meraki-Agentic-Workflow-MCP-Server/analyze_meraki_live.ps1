$envPath = Join-Path (Get-Location) '.env'
if (!(Test-Path $envPath)) { throw '.env not found' }

$kv = @{}
Get-Content $envPath | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $i = $_.IndexOf('=')
  if ($i -gt 0) {
    $k = $_.Substring(0,$i).Trim()
    $v = $_.Substring($i+1)
    $kv[$k] = $v
  }
}

$dashboardHost = $kv['MERAKI_DASHBOARD_HOST']
$csrf = $kv['MERAKI_CSRF_TOKEN']
$referer = $kv['MERAKI_REFERER']
$pageload = $kv['MERAKI_PAGELOAD_REQUEST_ID']
$cookiesRaw = $kv['MERAKI_COOKIES']

if (-not $dashboardHost -or -not $cookiesRaw) { throw 'MERAKI_DASHBOARD_HOST or MERAKI_COOKIES missing in .env' }

$networkId = 'L_656399645689271382'
$base = "https://$dashboardHost/api/v1"

$headers = @{
  'Accept' = 'application/json'
  'Content-Type' = 'application/json'
  'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
}
if ($csrf) { $headers['x-csrf-token'] = $csrf }
if ($referer) { $headers['referer'] = $referer }
if ($pageload) { $headers['x-pageload-request-id'] = $pageload }

$ws = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$cookieContainer = New-Object System.Net.CookieContainer
$cookiesRaw.Split(';') | ForEach-Object {
  $part = $_.Trim()
  if ($part -and $part.Contains('=')) {
    $name,$value = $part.Split('=',2)
    $cookie = New-Object System.Net.Cookie($name.Trim(), $value.Trim(), '/', $dashboardHost)
    $cookieContainer.Add($cookie)
  }
}
$ws.Cookies = $cookieContainer

function Invoke-MerakiGet([string]$url) {
  Invoke-RestMethod -Method Get -Uri $url -Headers $headers -WebSession $ws -TimeoutSec 40 -ErrorAction Stop
}

$network = Invoke-MerakiGet "$base/networks/$networkId"
$devices = Invoke-MerakiGet "$base/networks/$networkId/devices"
$alerts = Invoke-MerakiGet "$base/networks/$networkId/health/alerts"
$deviceStatuses = @()
$uplinks = @()
if ($network.organizationId) {
  $deviceStatuses = Invoke-MerakiGet "$base/organizations/$($network.organizationId)/devices/statuses"
  $uplinks = Invoke-MerakiGet "$base/organizations/$($network.organizationId)/uplinks/statuses"
}

$networkDevices = @($devices)
$networkAlerts = @($alerts)
$orgDeviceStatuses = @($deviceStatuses)
$orgUplinks = @($uplinks)

$networkStatuses = @()
if ($orgDeviceStatuses.Count -gt 0) {
  $networkStatuses = $orgDeviceStatuses | Where-Object { $_.networkId -eq $networkId }
}

$statusGroups = @{}
foreach ($d in $networkStatuses) {
  $s = if ($d.status) { "$($d.status)" } else { 'unknown' }
  if (-not $statusGroups.ContainsKey($s)) { $statusGroups[$s] = 0 }
  $statusGroups[$s]++
}

$offline = $networkStatuses | Where-Object { $_.status -in @('offline','dormant') }
$alerting = $networkStatuses | Where-Object { $_.status -eq 'alerting' }

$netUplinks = @()
if ($orgUplinks.Count -gt 0) {
  $serials = @{}
  $networkDevices | ForEach-Object { if ($_.serial) { $serials[$_.serial] = $true } }
  $netUplinks = $orgUplinks | Where-Object { $_.serial -and $serials.ContainsKey($_.serial) }
}

$uplinkIssues = @()
foreach ($u in $netUplinks) {
  foreach ($up in @($u.uplinks)) {
    $st = "$($up.status)"
    if ($st -and $st -ne 'active' -and $st -ne 'ready') {
      $uplinkIssues += [pscustomobject]@{
        serial = $u.serial
        model = $u.model
        interface = $up.interface
        status = $st
        publicIp = $up.publicIp
      }
    }
  }
}

$highAlerts = $networkAlerts | Where-Object { ("$($_.severity)").ToLower() -in @('critical','high') }

$problemDevices = @($offline) + @($alerting)

$summary = [pscustomobject]@{
  timestamp = (Get-Date).ToString('o')
  dashboardHost = $dashboardHost
  network = [pscustomobject]@{
    id = $network.id
    name = $network.name
    organizationId = $network.organizationId
    productTypes = $network.productTypes
  }
  totals = [pscustomobject]@{
    devices = $networkDevices.Count
    statusRecords = $networkStatuses.Count
    alerts = $networkAlerts.Count
    highSeverityAlerts = @($highAlerts).Count
    uplinkRecordsInNetwork = @($netUplinks).Count
    uplinkIssues = @($uplinkIssues).Count
    offlineOrDormantDevices = @($offline).Count
    alertingDevices = @($alerting).Count
  }
  deviceStatusBreakdown = $statusGroups
  sampleProblemDevices = @($problemDevices | Select-Object -First 8 | Select-Object name,serial,model,status,lastReportedAt,publicIp)
  sampleHighAlerts = @($highAlerts | Select-Object -First 8)
  sampleUplinkIssues = @($uplinkIssues | Select-Object -First 8)
}

$summary | ConvertTo-Json -Depth 8
