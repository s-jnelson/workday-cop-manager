<#
.SYNOPSIS  Finance Tech CoP Manager watchdog — checks ports and restarts offline servers.
           Runs via Windows Task Scheduler every 30 minutes.
#>

$proj     = 'C:\Users\steve.a.nelson\workday-cop-manager'
$logs     = Join-Path $proj 'logs'
$watchLog = Join-Path $logs 'watchdog.log'

if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs -Force | Out-Null }

$ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
function wlog { param([string]$m); Add-Content -Path $watchLog -Value "[$ts] $m" -Encoding UTF8 }
function isup { param([int]$p); return [bool](netstat -ano | Select-String ":$p\s.*LISTEN") }

wlog '--- Watchdog check started ---'

$restartCount = 0

# Dashboard (3030)
if (isup 3030) {
    wlog 'OK        : Dashboard (3030)'
} else {
    wlog 'RESTARTING: Dashboard (3030) was DOWN'
    $sp = @{ FilePath='python'; ArgumentList=@('-m','http.server','3030','--directory','dashboard'); WorkingDirectory=$proj; RedirectStandardOutput=(Join-Path $logs 'dashboard.log'); RedirectStandardError=(Join-Path $logs 'dashboard-err.log'); WindowStyle='Hidden' }
    Start-Process @sp
    $restartCount++
}

# API Server (8000)
if (isup 8000) {
    wlog 'OK        : API Server (8000)'
} else {
    wlog 'RESTARTING: API Server (8000) was DOWN'
    $sp = @{ FilePath='python'; ArgumentList=@('-m','uvicorn','api.server:app','--host','0.0.0.0','--port','8000'); WorkingDirectory=$proj; RedirectStandardOutput=(Join-Path $logs 'api.log'); RedirectStandardError=(Join-Path $logs 'api-err.log'); WindowStyle='Hidden' }
    Start-Process @sp
    $restartCount++
}

# Address & Banking Validator (8090)
if (isup 8090) {
    wlog 'OK        : Addr. Validator (8090)'
} else {
    wlog 'RESTARTING: Addr. Validator (8090) was DOWN'
    $sp = @{ FilePath='python'; ArgumentList=@('assets/files/ai/solutions/08_address_banking_validator/app.py'); WorkingDirectory=$proj; RedirectStandardOutput=(Join-Path $logs 'validator.log'); RedirectStandardError=(Join-Path $logs 'validator-err.log'); WindowStyle='Hidden' }
    Start-Process @sp
    $restartCount++
}

if ($restartCount -gt 0) {
    wlog "Waiting 12s to confirm $restartCount restarted server(s)..."
    Start-Sleep 12
    if (isup 3030) { wlog 'CONFIRMED : Dashboard (3030) is UP' } else { wlog 'FAILED    : Dashboard (3030) still DOWN — check dashboard-err.log' }
    if (isup 8000) { wlog 'CONFIRMED : API Server (8000) is UP' } else { wlog 'FAILED    : API Server (8000) still DOWN — check api-err.log' }
    if (isup 8090) { wlog 'CONFIRMED : Addr. Validator (8090) is UP' } else { wlog 'FAILED    : Addr. Validator (8090) still DOWN — check validator-err.log' }
}

wlog '--- Watchdog check complete ---'

$lines = Get-Content -Path $watchLog -Encoding UTF8 -ErrorAction SilentlyContinue
if ($lines -and $lines.Count -gt 500) {
    $lines | Select-Object -Last 500 | Set-Content -Path $watchLog -Encoding UTF8
}
