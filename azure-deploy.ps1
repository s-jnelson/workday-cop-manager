<#
.SYNOPSIS
    Deploy CoP Manager to Azure App Service (public HTTPS URL, no Docker required).

.PARAMETER ResourceGroup
    Azure Resource Group (default: cop-manager-rg)

.PARAMETER Location
    Azure region (default: eastus2)

.PARAMETER AppName
    Web App name — becomes part of the URL (default: cop-manager-[random])

.PARAMETER AnthropicKey
    Optional. Anthropic API key for the CoP Agent chat feature.

.EXAMPLE
    .\azure-deploy.ps1

.NOTES
    Prerequisites: none — Azure CLI is installed automatically if missing (requires winget)
    Deployment method: az webapp up (Python zip deploy — no Docker, no Container Registry)
    Run from: C:\Users\steve.a.nelson\workday-cop-manager\
#>

param(
    [string]$ResourceGroup = "cop-manager-rg",
    [string]$Location      = "eastus2",
    [string]$AppName       = "",
    [string]$AnthropicKey  = ""
)

Set-Location $PSScriptRoot

# Generate unique app name if not provided (must be globally unique for .azurewebsites.net)
if (-not $AppName) {
    $AppName = "cop-manager-$(Get-Random -Maximum 99999)"
}

Write-Host ""
Write-Host "=== CoP Manager — Azure Deployment ===" -ForegroundColor Cyan
Write-Host "Resource Group : $ResourceGroup"
Write-Host "Location       : $Location"
Write-Host "App Name       : $AppName"
Write-Host "URL (preview)  : https://$AppName.azurewebsites.net"
if ($AnthropicKey) {
    Write-Host "API Key        : provided (CoP Agent enabled)" -ForegroundColor Green
} else {
    Write-Host "API Key        : not provided (CoP Agent chat disabled)" -ForegroundColor Yellow
}
Write-Host ""

# ── 0. Ensure Azure CLI is installed ───────────────────────────────────────
$azPath = Get-Command az -ErrorAction SilentlyContinue
if (-not $azPath) {
    Write-Host "[0/5] Installing Azure CLI via winget..." -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host "ERROR: winget not available. Install Azure CLI from: https://aka.ms/installazurecliwindows" -ForegroundColor Red
        exit 1
    }
    winget install --id Microsoft.AzureCLI --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Azure CLI install failed. Install from: https://aka.ms/installazurecliwindows" -ForegroundColor Red
        exit 1
    }
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
    Write-Host "     Azure CLI installed." -ForegroundColor Green
    Write-Host ""
}

# ── 1. Verify Azure CLI login ───────────────────────────────────────────────
Write-Host "[1/5] Checking Azure login..." -ForegroundColor Yellow
$null = az account show 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "     Not logged in — opening browser for az login..." -ForegroundColor Gray
    az login
    if ($LASTEXITCODE -ne 0) { Write-Host "Login failed." -ForegroundColor Red; exit 1 }
}
$acct = az account show | ConvertFrom-Json
Write-Host "     Logged in as: $($acct.user.name)  (sub: $($acct.id))" -ForegroundColor Green

# ── 2. Create resource group ────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/5] Creating resource group '$ResourceGroup' in $Location..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output none
if ($LASTEXITCODE -ne 0) { Write-Host "Resource group creation failed." -ForegroundColor Red; exit 1 }
Write-Host "     Done." -ForegroundColor Green

# ── 3. Deploy via az webapp up (Python zip deploy — no Docker, no ACR) ──────
Write-Host ""
Write-Host "[3/5] Deploying to Azure App Service (Python 3.12)..." -ForegroundColor Yellow
Write-Host "      (Packages and uploads source — 2-4 minutes)" -ForegroundColor Gray
Write-Host ""

az webapp up `
    --name $AppName `
    --resource-group $ResourceGroup `
    --location $Location `
    --runtime "PYTHON:3.12" `
    --sku B1

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Deployment failed. Trying Python 3.11 runtime..." -ForegroundColor Yellow
    az webapp up `
        --name $AppName `
        --resource-group $ResourceGroup `
        --location $Location `
        --runtime "PYTHON:3.11" `
        --sku B1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Deployment failed. Check the error above." -ForegroundColor Red
        exit 1
    }
}

# ── 4. Configure startup command and port ───────────────────────────────────
Write-Host ""
Write-Host "[4/5] Configuring startup command and port..." -ForegroundColor Yellow

az webapp config set `
    --name $AppName `
    --resource-group $ResourceGroup `
    --startup-file "python dashboard_server.py" `
    --output none

$settings = @("WEBSITES_PORT=3030", "API_SERVER_URL=http://localhost:8000", "SCM_DO_BUILD_DURING_DEPLOYMENT=true")
if ($AnthropicKey) { $settings += "ANTHROPIC_API_KEY=$AnthropicKey" }

az webapp config appsettings set `
    --name $AppName `
    --resource-group $ResourceGroup `
    --settings $settings `
    --output none

Write-Host "     Done." -ForegroundColor Green

# ── 5. Restart to apply settings ────────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] Restarting app to apply settings..." -ForegroundColor Yellow
az webapp restart --name $AppName --resource-group $ResourceGroup --output none
Write-Host "     Done." -ForegroundColor Green

# ── Done ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Shareable URL:" -ForegroundColor White
Write-Host "  https://$AppName.azurewebsites.net" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Share with anyone — no VPN required." -ForegroundColor White
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Note: App may take 30-60 seconds to start on first visit." -ForegroundColor Gray
Write-Host ""
Write-Host "To redeploy after code changes:" -ForegroundColor Gray
Write-Host "  .\azure-deploy.ps1 -AppName $AppName" -ForegroundColor Gray
Write-Host ""
Write-Host "To tear down all Azure resources:" -ForegroundColor Gray
Write-Host "  az group delete --name $ResourceGroup --yes" -ForegroundColor Gray
