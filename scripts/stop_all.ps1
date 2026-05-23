# EIDOLON OS — Stop All Services
# Run from repo root: .\scripts\stop_all.ps1
#
# Kills any uvicorn process on port 8010 and Node.js process on port 3000.

$ErrorActionPreference = "SilentlyContinue"

Write-Host "`n=== EIDOLON OS — Stopping Services ===" -ForegroundColor Cyan

# ── Kill port 8010 (FastAPI/uvicorn) ─────────────────────────────────────────
$api = netstat -ano | Select-String ":8010 " | Select-String "LISTENING"
if ($api) {
    $pid8010 = ($api -split '\s+')[-1]
    Write-Host "Stopping FastAPI (PID $pid8010) on port 8010..." -ForegroundColor Yellow
    Stop-Process -Id $pid8010 -Force -ErrorAction SilentlyContinue
    Write-Host "  Done." -ForegroundColor Green
} else {
    Write-Host "No process on port 8010." -ForegroundColor DarkGray
}

# ── Kill port 3000 (Next.js) ──────────────────────────────────────────────────
$web = netstat -ano | Select-String ":3000 " | Select-String "LISTENING"
if ($web) {
    $pid3000 = ($web -split '\s+')[-1]
    Write-Host "Stopping Next.js (PID $pid3000) on port 3000..." -ForegroundColor Yellow
    Stop-Process -Id $pid3000 -Force -ErrorAction SilentlyContinue
    Write-Host "  Done." -ForegroundColor Green
} else {
    Write-Host "No process on port 3000." -ForegroundColor DarkGray
}

Write-Host "`n=== All EIDOLON services stopped. ===" -ForegroundColor Green
