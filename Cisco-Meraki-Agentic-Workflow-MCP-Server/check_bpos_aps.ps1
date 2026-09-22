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
$orgId = '1534738'
$targetSerials = @('Q3KD-5MEC-VQDF', 'Q3KD-K9QS-QSWW', 'Q3KD-LWFX-X527')
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

$statuses = Invoke-RestMethod -Method Get -Uri "$base/organizations/$orgId/devices/statuses" -Headers $headers -WebSession $ws -TimeoutSec 40
$filtered = @($statuses) |
  Where-Object { $_.networkId -eq $networkId -and $targetSerials -contains $_.serial } |
  Select-Object name, serial, model, status, lastReportedAt, publicIp, gateway, primaryDns

$filtered | ConvertTo-Json -Depth 5
