# EIDOLON OS — Electron Desktop Plan

## Overview

Electron embeds Chromium + Node.js and wraps the EIDOLON web stack.
Larger bundle (~120 MB) but zero Rust requirement — easier for rapid prototyping.
Use Tauri plan if bundle size matters.

## Prerequisites

```powershell
npm install --save-dev electron electron-builder concurrently wait-on
```

## Proposed structure

```
eidolon-os/
  desktop/
    electron/
      main.js          # Electron main process
      preload.js       # Context bridge (IPC)
      tray.js          # System tray
      package.json     # Electron build config
```

## Minimal main.js

```javascript
const { app, BrowserWindow, Tray, Menu, nativeImage, shell } = require('electron')
const { spawn } = require('child_process')
const path = require('path')

let mainWindow, tray, apiProcess

function startApi() {
  // Launch FastAPI via uvicorn
  apiProcess = spawn('python', ['-m', 'uvicorn', 'main:app', '--port', '8010'], {
    cwd: path.join(__dirname, '../../apps/api'),
    stdio: 'inherit',
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true },
    titleBarStyle: 'hidden',
    backgroundColor: '#0a0a0f',
  })
  // Wait for Next.js dev server, or load static build
  mainWindow.loadURL('http://localhost:3000')
}

function buildTray() {
  const icon = nativeImage.createFromPath(path.join(__dirname, 'icon.png'))
  tray = new Tray(icon.resize({ width: 16 }))
  const menu = Menu.buildFromTemplate([
    { label: 'Open EIDOLON', click: () => mainWindow?.show() },
    { label: 'Quick Recall', click: () => mainWindow?.webContents.send('quick-recall') },
    { type: 'separator' },
    { label: 'Quit', click: () => { app.quit() } },
  ])
  tray.setContextMenu(menu)
  tray.setToolTip('EIDOLON OS')
}

app.whenReady().then(() => {
  startApi()
  createWindow()
  buildTray()
})

app.on('before-quit', () => { apiProcess?.kill() })
```

## package.json (inside desktop/electron/)

```json
{
  "name": "eidolon-desktop",
  "version": "1.0.0",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "build": "electron-builder"
  },
  "build": {
    "appId": "os.eidolon.app",
    "productName": "EIDOLON OS",
    "win": {
      "target": ["nsis"],
      "icon": "icon.ico"
    },
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true
    },
    "files": ["**/*", "../../storage/**"]
  }
}
```

## Auto-start with Windows

```javascript
app.setLoginItemSettings({
  openAtLogin: true,
  path: app.getPath('exe'),
})
```

## Build for release

```powershell
cd desktop/electron
npm install
npm run build
# Output: desktop/electron/dist/EIDOLON OS Setup.exe
```

## Trade-offs vs Tauri

| Concern         | Electron                  | Tauri                         |
|-----------------|---------------------------|-------------------------------|
| Bundle size     | ~120 MB (Chromium)        | ~8 MB (OS webview)            |
| Startup speed   | ~2–3s                     | <1s                           |
| Rust required   | No                        | Yes                           |
| Node.js in main | Yes (full API)            | No (Rust + JS bridge)         |
| Maturity        | Very mature (VS Code etc) | Newer, fast-growing           |
| Recommendation  | Prototyping / fast path   | Production / distribution     |
