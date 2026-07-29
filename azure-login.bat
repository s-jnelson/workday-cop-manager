@echo off
title Step 1 - Azure Login
cd /d "%~dp0"
PowerShell.exe -NoExit -ExecutionPolicy Bypass -Command "Write-Host 'Logging into Azure - a browser window will open.' -ForegroundColor Cyan; Write-Host ''; az login"
