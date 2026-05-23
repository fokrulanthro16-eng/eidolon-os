# EIDOLON OS — Tauri Desktop Plan

## Overview

Tauri wraps the Next.js frontend in a native Rust webview window.
The FastAPI backend runs as a sidecar process managed by Tauri.
Final artifact: a single `.exe` installer (~8–15 MB, no Chromium).

## Prerequisites

```powershell
# Install Rust toolchain (one-time)
winget install Rustlang.Rustup
rustup update stable

# Install Tauri CLI
npm install --save-dev @tauri-apps/cli@next
```

## Proposed structure

```
eidolon-os/
  apps/
    web/           # existing Next.js app (no changes needed)
    api/           # existing FastAPI backend
  desktop/
    tauri/
      src-tauri/
        src/
          main.rs         # Tauri entrypoint + sidecar launch
          tray.rs         # System tray menu
          notifications.rs # Native OS notifications
        tauri.conf.json   # Build config, sidecar, permissions
        Cargo.toml
```

## Implementation steps

### Step 1 — Scaffold Tauri app
```powershell
cd apps/web
npx tauri init
```
Point Tauri's `distDir` to Next.js static export (`out/`).

### Step 2 — Configure sidecar (FastAPI daemon)
In `tauri.conf.json`:
```json
{
  "tauri": {
    "bundle": {
      "externalBin": ["binaries/eidolon-api"]
    }
  }
}
```
Build the API as a PyInstaller binary:
```powershell
pip install pyinstaller
pyinstaller --onefile apps/api/main.py -n eidolon-api
```
Place the EXE in `src-tauri/binaries/eidolon-api-x86_64-pc-windows-msvc.exe`.

### Step 3 — System tray
```rust
// src-tauri/src/tray.rs
use tauri::{SystemTray, SystemTrayMenu, CustomMenuItem};

pub fn build_tray() -> SystemTray {
    let capture   = CustomMenuItem::new("capture", "Quick Capture");
    let recall    = CustomMenuItem::new("recall",  "Quick Recall");
    let dashboard = CustomMenuItem::new("dashboard", "Open Dashboard");
    let quit      = CustomMenuItem::new("quit",    "Quit EIDOLON");
    let menu = SystemTrayMenu::new()
        .add_item(capture)
        .add_item(recall)
        .add_native_item(tauri::SystemTrayMenuItem::Separator)
        .add_item(dashboard)
        .add_native_item(tauri::SystemTrayMenuItem::Separator)
        .add_item(quit);
    SystemTray::new().with_menu(menu)
}
```

### Step 4 — Auto-start with Windows
```rust
use tauri_plugin_autostart::MacosLauncher;
// In main.rs:
tauri::Builder::default()
    .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, None))
```

### Step 5 — Build for release
```powershell
cd apps/web && npm run build  # generates out/
cd ../..
npx tauri build
# Output: src-tauri/target/release/bundle/msi/EIDOLON_OS_*.msi
```

## Key Tauri plugins needed

| Plugin                      | Purpose                        |
|-----------------------------|--------------------------------|
| tauri-plugin-autostart      | Start with Windows             |
| tauri-plugin-notification   | Native OS notifications        |
| tauri-plugin-global-shortcut| Hot-key screen capture         |
| tauri-plugin-single-instance| Prevent duplicate processes    |

## Notes

- Next.js must be configured for `output: 'export'` (static) in `next.config.js`
- The FastAPI sidecar communicates with the frontend via `http://127.0.0.1:8010`
- All data stays local — the sidecar writes to `storage/` in the app data dir
- Tauri's IPC bridge (`invoke`) can be used for native screenshot triggers
