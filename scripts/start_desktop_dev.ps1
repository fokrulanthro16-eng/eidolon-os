# EIDOLON OS — Desktop Dev Mode (Tauri or Electron)
# Run from repo root: .\scripts\start_desktop_dev.ps1
#
# This script is a PLACEHOLDER for the future desktop shell.
# EIDOLON OS currently runs as a local web OS — no desktop wrapper is required.
#
# When ready to develop the desktop shell:
#   Tauri:    cd desktop/tauri && npm run tauri dev
#   Electron: cd desktop/electron && npm start
#
# For now, this script launches the standard web stack.

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "`n=== EIDOLON OS — Desktop Dev Mode ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Desktop shell status: PLANNED (Phase 19)" -ForegroundColor Yellow
Write-Host "  - Tauri plan:    desktop\tauri-plan.md" -ForegroundColor DarkGray
Write-Host "  - Electron plan: desktop\electron-plan.md" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Launching standard web stack instead..." -ForegroundColor Cyan
Write-Host ""

# Fall back to the standard start_all script
& "$PSScriptRoot\start_all.ps1"
