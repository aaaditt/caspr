/**
 * hotkeys.js — Global shortcut registration for push-to-talk and actions.
 *
 * Electron's globalShortcut doesn't support push-to-talk (press/release),
 * so we use a combination approach:
 * - For modifier-only chords (like Win+Z), we use globalShortcut for
 *   reliable registration and send press on trigger, release on a short delay.
 * - The actual hold-to-talk behavior is handled by the Python backend's
 *   keyboard hook for now, since Electron can't detect key release events
 *   for global shortcuts.
 *
 * For Phase 1 we keep the Python `keyboard` library for PTT (press/release)
 * and use Electron globalShortcut only for the action hotkeys (toggle, cancel,
 * mute, open history) which are simple press-and-release shortcuts.
 */

const { globalShortcut } = require('electron');

// Map from Python keyboard-lib chord format to Electron accelerator format
const KEY_MAP = {
  'ctrl': 'CommandOrControl',
  'alt': 'Alt',
  'shift': 'Shift',
  'windows': 'Super',
  'win': 'Super',
  'space': 'Space',
  'enter': 'Return',
  'esc': 'Escape',
  'tab': 'Tab',
  'backspace': 'Backspace',
  'delete': 'Delete',
  'up': 'Up',
  'down': 'Down',
  'left': 'Left',
  'right': 'Right',
  // Function keys
  'f1': 'F1', 'f2': 'F2', 'f3': 'F3', 'f4': 'F4',
  'f5': 'F5', 'f6': 'F6', 'f7': 'F7', 'f8': 'F8',
  'f9': 'F9', 'f10': 'F10', 'f11': 'F11', 'f12': 'F12',
};

/**
 * Convert a Python keyboard-lib chord string to an Electron accelerator.
 * "ctrl+windows" → "CommandOrControl+Super"
 * "windows+z" → "Super+Z"
 */
function toAccelerator(chord) {
  if (!chord) return null;
  const parts = chord.split('+').map(p => p.trim().toLowerCase());
  const mapped = parts.map(p => {
    if (KEY_MAP[p]) return KEY_MAP[p];
    // Single letter or number keys: uppercase
    if (p.length === 1) return p.toUpperCase();
    // Sided modifiers: "right ctrl" → "CommandOrControl"
    const unsided = p.replace(/^(left|right)\s+/, '');
    if (KEY_MAP[unsided]) return KEY_MAP[unsided];
    return p; // fallback
  });
  return mapped.join('+');
}

class HotkeyManager {
  constructor(wsClient) {
    this._wsClient = wsClient;
    this._registered = new Map(); // accelerator → handler
  }

  /**
   * Register action hotkeys (not PTT — that stays in Python for now).
   * @param {Object} hotkeys - Map of action name → chord string
   *   e.g. { hotkey_toggle_dictation: "ctrl+shift+d", hotkey_mute_mic: "" }
   */
  registerActions(hotkeys) {
    this.unregisterAll();

    for (const [action, chord] of Object.entries(hotkeys)) {
      if (!chord) continue;
      const accel = toAccelerator(chord);
      if (!accel) continue;

      try {
        const success = globalShortcut.register(accel, () => {
          console.log(`[hotkeys] ${action} triggered (${accel})`);
          // Map action names to WebSocket messages
          if (action === 'hotkey_toggle_dictation') {
            this._wsClient.send({ type: 'toggle_pause' });
          } else if (action === 'hotkey_mute_mic') {
            this._wsClient.send({ type: 'toggle_pause' });
          } else if (action === 'hotkey_open_history') {
            // Show the main window on history page
            const { BrowserWindow } = require('electron');
            const wins = BrowserWindow.getAllWindows();
            if (wins.length > 0) {
              wins[0].show();
              wins[0].focus();
              wins[0].webContents.send('navigate', 'history');
            }
          }
        });
        if (success) {
          this._registered.set(accel, action);
          console.log(`[hotkeys] registered ${action}: ${accel}`);
        } else {
          console.warn(`[hotkeys] failed to register ${action}: ${accel}`);
        }
      } catch (err) {
        console.warn(`[hotkeys] error registering ${action}: ${err.message}`);
      }
    }
  }

  unregisterAll() {
    for (const accel of this._registered.keys()) {
      try {
        globalShortcut.unregister(accel);
      } catch { /* ignore */ }
    }
    this._registered.clear();
  }
}

module.exports = { HotkeyManager, toAccelerator };
