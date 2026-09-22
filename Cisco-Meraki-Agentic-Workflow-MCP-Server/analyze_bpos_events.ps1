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

function Invoke-MerakiGet([string]$url) {
  Invoke-RestMethod -Method Get -Uri $url -Headers $headers -WebSession $ws -TimeoutSec 45 -ErrorAction Stop
}

# Identify active B_POS clients first (last 24h)
$clients24h = Invoke-MerakiGet "$base/networks/$networkId/clients?timespan=86400&perPage=250"
$bposClients = @($clients24h) | Where-Object { ("$($_.ssid)").Trim() -eq $ssidName }

$signalsRegex = 'disassoc|deauth|auth|roam|rssi|dhcp|eapol|timeout|failed|failure|disconnect|unreachable|ip conflict|association'
$clientAnalyses = @()

foreach ($client in $bposClients) {
  $clientId = $client.id
  $mac = $client.mac

  # Try network-scoped events for this client in last 24h
  $eventsUrl = "$base/networks/$networkId/events?productType=wireless&clientId=$clientId&perPage=200"
  $events = @()
  try {
    $eventsResponse = Invoke-MerakiGet $eventsUrl
    if ($eventsResponse.events) {
      $events = @($eventsResponse.events)
    }
    else {
      $events = @($eventsResponse)
    }
  }
  catch {
    $events = @()
  }

  $eventMatches = @()
  foreach ($e in $events) {
    $blob = ($e | ConvertTo-Json -Depth 6)
    if ($blob -match $signalsRegex) {
      $eventMatches += $e
    }
  }

  $clientAnalyses += [pscustomobject]@{
    description = $client.description
    mac = $mac
    ip = $client.ip
    manufacturer = $client.manufacturer
    recentDeviceName = $client.recentDeviceName
    recentDeviceSerial = $client.recentDeviceSerial
    status = $client.status
    totalWirelessEvents24h = @($events).Count
    signalEventCount24h = @($eventMatches).Count
    sampleSignalEvents = @($eventMatches | Select-Object -First 10)
  }
}

# Aggregate keywords for quick triage
$keywords = @('deauth','disassoc','dhcp','roam','timeout','failed','failure','rssi','association')
$keywordCounts = @{}
foreach ($k in $keywords) { $keywordCounts[$k] = 0 }

foreach ($ca in $clientAnalyses) {
  foreach ($ev in @($ca.sampleSignalEvents)) {
    $blob = ($ev | ConvertTo-Json -Depth 6).ToLower()
    foreach ($k in $keywords) {
      if ($blob -match [regex]::Escape($k)) { $keywordCounts[$k]++ }
    }
  }
}

$result = [pscustomobject]@{
  timestamp = (Get-Date).ToString('o')
  networkId = $networkId
  ssid = $ssidName
  clientCount24h = @($bposClients).Count
  clients = $clientAnalyses
  keywordSignalCountsFromSamples = $keywordCounts
}

$result | ConvertTo-Json -Depth 8
