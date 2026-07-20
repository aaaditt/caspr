/**
 * tray.js — System tray icon with context menu.
 */

const { Tray, Menu, nativeImage, app } = require('electron');
const path = require('path');

let tray = null;

function createTray(mainWindow, wsClient) {
  // Use a simple 16x16 icon; fall back to app icon
  const iconPath = path.join(__dirname, 'icon.png');
  let icon;
  try {
    icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } catch {
    icon = nativeImage.createEmpty();
  }

  tray = new Tray(icon);
  tray.setToolTip('caspr — voice dictation');

  const updateMenu = (paused = false) => {
    const menu = Menu.buildFromTemplate([
      {
        label: 'Show caspr',
        click: () => {
          mainWindow.show();
          mainWindow.focus();
        },
      },
      { type: 'separator' },
      {
        label: paused ? 'Resume dictation' : 'Pause dictation',
        click: () => {
          wsClient.send({ type: 'toggle_pause' });
        },
      },
      { type: 'separator' },
      {
        label: 'Quit caspr',
        click: () => {
          app.isQuitting = true;
          app.quit();
        },
      },
    ]);
    tray.setContextMenu(menu);
  };

  updateMenu();

  // Update menu when pause state changes
  wsClient.on('paused_changed', (msg) => {
    updateMenu(msg.paused);
  });

  tray.on('double-click', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  return tray;
}

function destroyTray() {
  if (tray) {
    tray.destroy();
    tray = null;
  }
}

module.exports = { createTray, destroyTray };
