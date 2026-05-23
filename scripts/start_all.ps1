# EIDOLON OS — Start All Services
# Run from repo root: .\scripts\start_all.ps1
#
# Starts:
#   1. FastAPI backend  (port 8010) in a new PowerShell window
#   2. Next.js frontend (port 3000) in a new PowerShell window
#
# Requirements:
#   - Python venv at .venv-312\Scripts\
#   - Node.js installed
#   - Run setup_venv.ps1 first if not already set up

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "`n=== EIDOLON OS — Starting All Services ===" -ForegroundColor Cyan

# ── 1. Verify venv exists ─────────────────────────────────────────────────────
$venvPython = Join-Path $ROOT ".venv-312\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: Virtual environment not found at .venv-312" -ForegroundColor Red
    Write-Host "Run: .\scripts\setup_venv.ps1" -ForegroundColor Yellow
    exit 1
}

# ── 2. Start FastAPI backend ──────────────────────────────────────────────────
Write-Host "`n[1/2] Starting FastAPI backend on http://127.0.0.1:8010 ..." -ForegroundColor Yellow
$apiCmd = "Set-Location '$ROOT\apps\api'; & '$venvPython' -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCmd -WindowStyle Normal

# Brief pause so the API has a head start
Start-Sleep -Seconds 2

# ── 3. Start Next.js frontend ─────────────────────────────────────────────────
Write-Host "[2/2] Starting Next.js frontend on http://localhost:3000 ..." -ForegroundColor Yellow
$webCmd = "Set-Location '$ROOT\apps\web'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $webCmd -WindowStyle Normal

Write-Host "`n=== Both services launched ===" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Backend:   http://127.0.0.1:8010" -ForegroundColor Cyan
Write-Host "  API docs:  http://127.0.0.1:8010/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop all services run: .\scripts\stop_all.ps1" -ForegroundColor DarkGray
