# Run EIDOLON OS API from the project root
# Usage: .\start_api.ps1

$env:PYTHONPATH = $PSScriptRoot
Set-Location $PSScriptRoot

Write-Host "Starting EIDOLON OS API..." -ForegroundColor Cyan
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
