# TriStar Modal Deployment Script (PowerShell)
# ASCII-safe version - no emoji to avoid encoding issues

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

Write-Host "TriStar Modal Deployment" -ForegroundColor Cyan
Write-Host ("=" * 50)
Write-Host "UTF-8 encoding configured" -ForegroundColor Green

# Check modal CLI
$modalCheck = modal --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Modal CLI not found. Installing..." -ForegroundColor Yellow
    pip install modal
}
Write-Host "Modal CLI ready: $modalCheck" -ForegroundColor Green

# Deploy
Write-Host ""
Write-Host "Deploying to Modal..." -ForegroundColor Cyan
modal deploy modal_app.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Deployment successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Test your endpoints:" -ForegroundColor Cyan
    Write-Host "  Health: https://bhuvansingh6p--tristar-api-fastapi-app.modal.run/health"
    Write-Host "  Docs:   https://bhuvansingh6p--tristar-api-fastapi-app.modal.run/docs"
    Write-Host "  Deals:  https://bhuvansingh6p--tristar-api-fastapi-app.modal.run/api/designer/live-deals"
} else {
    Write-Host ""
    Write-Host "Deployment failed. Check errors above." -ForegroundColor Red
}
