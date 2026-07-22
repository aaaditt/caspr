/**
 * main.js — Electron main process.
 *
 * Creates the app window, spawns the Python backend, connects via WebSocket,
 * sets up the system tray and global hotkeys.
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { PythonBackend } = require('./python');
const { WsClient } = require('./ws-client');
const { createTray, destroyTray } = require('./tray');

const WS_PORT = 18321;
const isDev = !!process.env.CASPR_UI_DEV;

let mainWindow = null;
let python = null;
let wsClient = null;
// Global hotkeys (primary PTT + action keys) are owned by the Python backend —
// Electron's globalShortcut can't detect key-release for hold-to-talk. The main
// process only reacts to window actions the backend broadcasts (e.g. open history).

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 940,
    height: 600,
    minWidth: 760,
    minHeight: 480,
    frame: false,
    transparent: false,
    backgroundColor: '#151110',
    show: false,
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Rounded corners on Windows 11
  mainWindow.setBackgroundMaterial?.('none');

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173/');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    const distPath = path.resolve(__dirname, '..', 'webui', 'dist', 'index.html');
    mainWindow.loadFile(distPath);
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Close hides to tray (like the Qt version)
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

function setupIpc() {
  // Window controls from the renderer
  ipcMain.on('win-minimize', () => mainWindow?.minimize());
  ipcMain.on('win-close', () => mainWindow?.hide());
  ipcMain.on('win-drag', () => {
    // Electron doesn't have startSystemMove, but the CSS -webkit-app-region: drag
    // handles this in the renderer. This is a fallback.
  });
  ipcMain.on('win-resize', (_e, edge) => {
    // Electron handles resize via CSS resize handles or native frame
    // For frameless windows, the ResizeEdges component handles this
  });

  // WebSocket pass-through: fire-and-forget
  ipcMain.on('ws-send', (_e, msg) => {
    wsClient?.send(msg);
  });

  // WebSocket pass-through: request/response
  ipcMain.handle('ws-request', async (_e, msg) => {
    if (!wsClient?.connected) return null;
    try {
      return await wsClient.request(msg, 10000);
    } catch (err) {
      console.error('[ipc] ws-request failed:', err.message);
      return null;
    }
  });

  // Hotkey capture — routed to Python's Qt dialog (can see all keys inc. Windows)
  ipcMain.handle('capture-hotkey', async () => {
    if (!wsClient?.connected) return null;
    try {
      const reply = await wsClient.request({ type: 'capture_hotkey' }, 20000);
      return reply?.chord || null;
    } catch (err) {
      console.error('[ipc] capture-hotkey failed:', err.message);
      return null;
    }
  });
}

function startBackend() {
  // 1. Spawn Python
  python = new PythonBackend(WS_PORT);
  python.start();

  // 2. Connect WebSocket (with auto-reconnect)
  wsClient = new WsClient(WS_PORT);

  wsClient.on('connected', () => {
    console.log('[main] WebSocket connected — Python owns the global hotkeys.');
  });

  // Forward WebSocket events to the renderer; act on window-action broadcasts.
  wsClient.on('event', (msg) => {
    if (msg.type === 'action' && msg.name === 'open_history') {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.show();
        mainWindow.focus();
        mainWindow.webContents.send('navigate', 'history');
      }
      return;
    }
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('ws-event', msg);
    }
  });

  // Wait a moment for Python to start, then connect
  setTimeout(() => wsClient.connect(), 2000);
}

// -- App lifecycle ----------------------------------------------------------

app.whenReady().then(() => {
  createWindow();
  setupIpc();
  startBackend();
  createTray(mainWindow, wsClient);
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  } else {
    mainWindow?.show();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
  destroyTray();
  wsClient?.disconnect();
  python?.stop();
});

app.on('window-all-closed', () => {
  // Don't quit — caspr runs in the tray
});

// Prevent multiple instances
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}
