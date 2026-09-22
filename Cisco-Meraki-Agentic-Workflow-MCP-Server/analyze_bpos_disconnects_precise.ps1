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
$ssidNumber = 7
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

function Invoke-MerakiGet([string]$url) {
  Invoke-RestMethod -Method Get -Uri $url -Headers $headers -WebSession $ws -TimeoutSec 50 -ErrorAction Stop
}

$clients24h = Invoke-MerakiGet "$base/networks/$networkId/clients?timespan=86400&perPage=250"
$bposClients = @($clients24h) | Where-Object { ("$($_.ssid)").Trim() -eq $ssidName }
$clientMacSet = @{}
foreach ($c in $bposClients) { if ($c.mac) { $clientMacSet[$c.mac.ToLower()] = $c } }

$eventsResp = Invoke-MerakiGet "$base/networks/$networkId/events?productType=wireless&perPage=1000"
$allEvents = @()
if ($eventsResp.events) { $allEvents = @($eventsResp.events) } else { $allEvents = @($eventsResp) }

$filteredEvents = @($allEvents) | Where-Object {
  $mac = ("$($_.clientMac)").ToLower()
  $matchMac = $clientMacSet.ContainsKey($mac)
  $matchSsid = ("$($_.ssidName)" -eq $ssidName) -or ($_.ssidNumber -eq $ssidNumber)
  $matchMac -or $matchSsid
}

$disconnectTypes = @('disassociation', 'wpa_deauth', 'assoc_status', 'client_disconnect', 'client_failed_connection')
$disconnectEvents = @($filteredEvents) | Where-Object { $disconnectTypes -contains ("$($_.type)") }

$disconnectByClient = @()
foreach ($c in $bposClients) {
  $mac = ("$($c.mac)").ToLower()
  $eventsForClient = @($disconnectEvents) | Where-Object { ("$($_.clientMac)").ToLower() -eq $mac }
  $lastEvent = $eventsForClient | Sort-Object occurredAt -Descending | Select-Object -First 1

  $reasonCodes = @($eventsForClient | ForEach-Object { "$($_.eventData.reason)" } | Where-Object { $_ -and $_ -ne '' })
  $reasonSummary = $reasonCodes | Group-Object | Sort-Object Count -Descending | Select-Object -First 3 Name,Count

  $disconnectByClient += [pscustomobject]@{
    description = $c.description
    mac = $c.mac
    recentDeviceName = $c.recentDeviceName
    recentDeviceSerial = $c.recentDeviceSerial
    disconnectEventCount24h = @($eventsForClient).Count
    lastDisconnectEventType = if ($lastEvent) { $lastEvent.type } else { $null }
    lastDisconnectAt = if ($lastEvent) { $lastEvent.occurredAt } else { $null }
    topReasonCodes = @($reasonSummary)
  }
}

$typeCounts = @($disconnectEvents | Group-Object type | Sort-Object Count -Descending | Select-Object Name,Count)

$result = [pscustomobject]@{
  timestamp = (Get-Date).ToString('o')
  networkId = $networkId
  ssid = $ssidName
  bposClientCount24h = @($bposClients).Count
  analyzedEventWindowCount = @($allEvents).Count
  filteredEventCount = @($filteredEvents).Count
  disconnectTypeCounts = $typeCounts
  disconnectByClient = $disconnectByClient
  sampleDisconnectEvents = @($disconnectEvents | Sort-Object occurredAt -Descending | Select-Object -First 12 occurredAt,type,description,clientDescription,clientMac,deviceName,ssidName,eventData)
}

$result | ConvertTo-Json -Depth 8
