@echo off
title Step 2 - Deploy CoP Manager to Azure
cd /d "%~dp0"
PowerShell.exe -NoExit -ExecutionPolicy Bypass -File "%~dp0azure-deploy.ps1"
