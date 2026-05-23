# EIDOLON OS — Desktop Shell (Planned)

This directory contains planning documents for the native desktop shell integration.
EIDOLON OS currently runs as a **local web OS** (FastAPI backend + Next.js frontend).
The desktop layer is the next evolution — wrapping the existing stack in a native shell
for tray access, system startup, and offline-first operation.

## Current status

| Layer        | Status              | Notes                                           |
|--------------|---------------------|-------------------------------------------------|
| FastAPI API  | ✅ Live              | Runs on port 8010                               |
| Next.js UI   | ✅ Live              | Runs on port 3000                               |
| Desktop shell| 🗺 Planned (Tauri)   | See `tauri-plan.md`                             |
| Electron alt | 🗺 Alternative plan  | See `electron-plan.md`                          |

## No installation required for current version

Run the existing stack with:

```powershell
# From repo root
.\scripts\start_all.ps1
```

Then open http://localhost:3000 in your browser.

## Desktop shell goals

- System tray icon with quick capture / quick recall
- Auto-start with Windows (background daemon)
- Native OS notifications for memory events
- Single-EXE distributable (Tauri) or installer (Electron)
- Hot-key screen capture without browser focus
- Offline-first: no browser required

## Recommended path: Tauri

See `tauri-plan.md`. Tauri bundles the Next.js static export + Rust webview.
Produces a small (~8 MB) single binary. Requires Rust toolchain.

## Alternative path: Electron

See `electron-plan.md`. Electron bundles Chromium — larger (~120 MB) but
zero Rust requirement. Easier for rapid prototyping.
