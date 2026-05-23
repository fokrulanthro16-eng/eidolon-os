# EIDOLON OS — Windows Setup Script
# Run from project root: .\scripts\setup_venv.ps1
# Requires: Python 3.12 installed (py launcher), Docker Desktop

param(
    [string]$Python312 = "py -3.12"
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "`n=== EIDOLON OS — Environment Setup ===" -ForegroundColor Cyan

# ── 1. Check Python 3.12 ─────────────────────────────────────────────────────
Write-Host "`n[1/6] Checking Python 3.12..." -ForegroundColor Yellow
try {
    $ver = Invoke-Expression "$Python312 --version"
    Write-Host "  Found: $ver" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python 3.12 not found." -ForegroundColor Red
    Write-Host "  Download: https://www.python.org/downloads/release/python-3129/" -ForegroundColor Red
    exit 1
}

# ── 2. Create .venv-312 ───────────────────────────────────────────────────────
Write-Host "`n[2/6] Creating Python 3.12 virtual environment..." -ForegroundColor Yellow
$venvPath = Join-Path $ROOT ".venv-312"
if (-not (Test-Path $venvPath)) {
    Invoke-Expression "$Python312 -m venv $venvPath"
    Write-Host "  Created: $venvPath" -ForegroundColor Green
} else {
    Write-Host "  Already exists: $venvPath" -ForegroundColor DarkGray
}

# ── 3. Install Python packages ────────────────────────────────────────────────
Write-Host "`n[3/6] Installing Python dependencies..." -ForegroundColor Yellow
$pip = Join-Path $venvPath "Scripts\pip.exe"
& $pip install --upgrade pip --quiet
& $pip install -r (Join-Path $ROOT "requirements.txt")
Write-Host "  Dependencies installed." -ForegroundColor Green

# ── 4. Docker infrastructure ──────────────────────────────────────────────────
Write-Host "`n[4/6] Starting Docker services (PostgreSQL + Redis)..." -ForegroundColor Yellow
$composeFile = Join-Path $ROOT "docker\docker-compose.yml"
try {
    docker compose -f $composeFile up -d
    Write-Host "  PostgreSQL + Redis started." -ForegroundColor Green
    Write-Host "  Waiting 5s for Postgres to initialize..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
} catch {
    Write-Host "  WARNING: Docker not available. Install Docker Desktop." -ForegroundColor Red
    Write-Host "  https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
}

# ── 5. Install Ollama ─────────────────────────────────────────────────────────
Write-Host "`n[5/6] Ollama setup..." -ForegroundColor Yellow
Write-Host "  Download Ollama from: https://ollama.com/download" -ForegroundColor DarkGray
Write-Host "  After install, run:" -ForegroundColor DarkGray
Write-Host "    ollama pull qwen2-vl:2b   (CPU, 1.5GB)" -ForegroundColor DarkGray
Write-Host "    ollama pull qwen2-vl:7b   (GPU, 4.7GB, better quality)" -ForegroundColor DarkGray

# ── 6. Create .env ────────────────────────────────────────────────────────────
Write-Host "`n[6/6] Creating .env from template..." -ForegroundColor Yellow
$envFile = Join-Path $ROOT ".env"
$exampleFile = Join-Path $ROOT ".env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $exampleFile $envFile
    Write-Host "  .env created from .env.example" -ForegroundColor Green
} else {
    Write-Host "  .env already exists — skipping." -ForegroundColor DarkGray
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Activate venv:  .\.venv-312\Scripts\Activate.ps1"
Write-Host "  2. Start API:      `$env:PYTHONPATH='$ROOT'; uvicorn apps.api.main:app --reload"
Write-Host "  3. Start worker:   celery -A apps.api.workers.celery_app worker --pool=solo -Q eidolon.ingest,eidolon.capture,eidolon.vision"
Write-Host "  4. Start Beat:     celery -A apps.api.workers.beat beat --loglevel=info"
Write-Host "  5. API docs:       http://localhost:8000/docs"
Write-Host ""
