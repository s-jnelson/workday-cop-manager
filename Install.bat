@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

title CoP Manager - Azure Installer
color 0B

echo.
echo  =====================================================
echo    CoP Manager  ^|  Azure Deployment Installer
echo  =====================================================
echo.
echo  This installer will automatically:
echo    [1] Install Azure CLI  (if not already installed)
echo    [2] Log you into Azure (browser window will open)
echo    [3] Build and deploy the dashboard to Azure
echo    [4] Print your shareable URL
echo.
echo  Time required: ~6 minutes on first run.
echo.
echo  Press any key to start, or close this window to cancel.
echo  -----------------------------------------------------
pause >nul
echo.

:: ── Check for PowerShell ─────────────────────────────────────────────────────
where powershell >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: PowerShell is required but was not found.
    echo  Install it from: https://aka.ms/powershell
    pause
    exit /b 1
)

:: ── Hand off to the deploy script (keeps window open via -NoExit) ────────────
echo  Starting installer...
echo.
PowerShell.exe -NoExit -ExecutionPolicy Bypass -File "%~dp0azure-deploy.ps1"
