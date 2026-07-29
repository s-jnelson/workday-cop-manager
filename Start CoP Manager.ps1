<#
.SYNOPSIS  Finance Tech CoP Manager — server startup script
#>
param()

$proj = 'C:\Users\steve.a.nelson\workday-cop-manager'
$logs = Join-Path $proj 'logs'

if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs -Force | Out-Null }

Write-Host ''
Write-Host '  ============================================================' -ForegroundColor DarkGray
Write-Host '   Finance Tech CoP Manager  —  Starting Servers' -ForegroundColor Cyan
Write-Host '  ============================================================' -ForegroundColor DarkGray
Write-Host ''

# Stop any existing processes on these ports
Write-Host '  Stopping any existing servers...' -ForegroundColor DarkGray
@(3030, 8000, 8090) | ForEach-Object {
    $port = $_
    netstat -ano | Select-String ":$port\s" | ForEach-Object {
        $pid_ = ($_ -split '\s+')[-1]
        if ($pid_ -match '^\d+$' -and $pid_ -ne '0') {
            Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
        }
    }
}
Start-Sleep 1

# Start Dashboard (port 3030)
Write-Host '  [1/3] Dashboard        -> http://localhost:3030' -ForegroundColor Cyan
Start-Process python `
    -ArgumentList '-m', 'http.server', '3030', '--directory', 'dashboard' `
    -WorkingDirectory $proj `
    -RedirectStandardOutput (Join-Path $logs 'dashboard.log') `
    -RedirectStandardError  (Join-Path $logs 'dashboard-err.log') `
    -WindowStyle Hidden

# Start API server (port 8000)
Write-Host '  [2/3] API Server       -> http://localhost:8000' -ForegroundColor Cyan
Start-Process python `
    -ArgumentList '-m', 'uvicorn', 'api.server:app', '--host', '0.0.0.0', '--port', '8000' `
    -WorkingDirectory $proj `
    -RedirectStandardOutput (Join-Path $logs 'api.log') `
    -RedirectStandardError  (Join-Path $logs 'api-err.log') `
    -WindowStyle Hidden

# Start Address & Banking Validator (port 8090)
Write-Host '  [3/3] Addr. Validator  -> http://localhost:8090' -ForegroundColor Cyan
Start-Process python `
    -ArgumentList 'assets/files/ai/solutions/08_address_banking_validator/app.py' `
    -WorkingDirectory $proj `
    -RedirectStandardOutput (Join-Path $logs 'validator.log') `
    -RedirectStandardError  (Join-Path $logs 'validator-err.log') `
    -WindowStyle Hidden

Write-Host ''
Write-Host '  Waiting for all servers to come online...' -ForegroundColor Yellow

$ready = $false
$secs  = 0
while (-not $ready -and $secs -lt 45) {
    Start-Sleep 1
    $secs++
    $p1 = netstat -ano | Select-String ':3030\s.*LISTEN'
    $p2 = netstat -ano | Select-String ':8000\s.*LISTEN'
    $p3 = netstat -ano | Select-String ':8090\s.*LISTEN'
    if ($p1 -and $p2 -and $p3) {
        $ready = $true
    } elseif ($secs % 5 -eq 0) {
        $up = @()
        if ($p1) { $up += '3030' }
        if ($p2) { $up += '8000' }
        if ($p3) { $up += '8090' }
        $upStr = if ($up.Count) { $up -join ', ' } else { 'none yet' }
        Write-Host "    Still starting... ${secs}s  (listening: $upStr)" -ForegroundColor DarkGray
    }
}

Write-Host ''
if ($ready) {
    Write-Host '  All servers online — opening dashboard...' -ForegroundColor Green
} else {
    Write-Host '  Warning: timeout reached — servers may still be starting.' -ForegroundColor Yellow
    Write-Host "  Check logs in: $logs" -ForegroundColor DarkGray
}

Start-Process 'http://localhost:3030'

Write-Host ''
Write-Host '  Servers are running in the background.' -ForegroundColor DarkGray
Write-Host '  You can safely close this window.' -ForegroundColor DarkGray
Write-Host ''
