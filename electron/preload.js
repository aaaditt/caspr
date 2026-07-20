/**
 * preload.js — Secure bridge between renderer and main process.
 *
 * Exposes a `window.caspr` API that matches the interface the React UI
 * expects (CasprApi from bridge.ts), so the existing React code works
 * with minimal changes.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Signal-like objects that the React code can .connect() / .disconnect()
function createSignal() {
  const listeners = new Set();
  return {
    connect(cb) { listeners.add(cb); },
    disconnect(cb) { listeners.delete(cb); },
    _emit(...args) { listeners.forEach(cb => cb(...args)); },
  };
}

const signals = {
  state_changed: createSignal(),
  input_level: createSignal(),
  dictation_done: createSignal(),
  paused_changed: createSignal(),
  data_changed: createSignal(),
};

// Listen for events pushed from the main process
ipcRenderer.on('ws-event', (_event, msg) => {
  switch (msg.type) {
    case 'state_changed':
      signals.state_changed._emit(msg.state, msg.detail);
      break;
    case 'input_level':
      signals.input_level._emit(msg.level);
      break;
    case 'dictation_done':
      signals.dictation_done._emit(msg.text, msg.spans);
      break;
    case 'paused_changed':
      signals.paused_changed._emit(msg.paused);
      break;
    case 'data_changed':
      signals.data_changed._emit();
      break;
  }
});

// Listen for navigation commands from main process
ipcRenderer.on('navigate', (_event, page) => {
  // Dispatch a custom event that the React app can listen for
  window.dispatchEvent(new CustomEvent('caspr-navigate', { detail: page }));
});

contextBridge.exposeInMainWorld('caspr', {
  // Window controls
  win_minimize: () => ipcRenderer.send('win-minimize'),
  win_close: () => ipcRenderer.send('win-close'),
  win_drag: () => ipcRenderer.send('win-drag'),
  win_resize: (edge) => ipcRenderer.send('win-resize', edge),

  // Data requests (callback style to match QWebChannel API)
  get_bootstrap: (cb) => {
    ipcRenderer.invoke('ws-request', { type: 'get_bootstrap' }).then(reply => {
      if (reply?.data) cb(reply.data);
    });
  },
  get_history: (query, cb) => {
    ipcRenderer.invoke('ws-request', { type: 'get_history', query }).then(reply => {
      if (reply?.data) cb(reply.data);
    });
  },
  get_dictionary: (cb) => {
    ipcRenderer.invoke('ws-request', { type: 'get_dictionary' }).then(reply => {
      if (reply?.data) cb(reply.data);
    });
  },

  // Fire-and-forget commands
  delete_entry: (id) => ipcRenderer.send('ws-send', { type: 'delete_entry', id }),
  copy_text: (text) => ipcRenderer.send('ws-send', { type: 'copy_text', text }),
  learn_term: (term) => ipcRenderer.send('ws-send', { type: 'learn_term', term }),
  forget_term: (term) => ipcRenderer.send('ws-send', { type: 'forget_term', term }),
  forget_rule: (wrong) => ipcRenderer.send('ws-send', { type: 'forget_rule', wrong }),
  set_setting: (key, value) => ipcRenderer.send('ws-send', { type: 'set_setting', key, value }),
  set_startup: (enabled) => ipcRenderer.send('ws-send', { type: 'set_startup', enabled }),
  toggle_pause: () => ipcRenderer.send('ws-send', { type: 'toggle_pause' }),

  // Correction popup — not available in Electron (stays as Python Qt dialog)
  correct: (text) => ipcRenderer.send('ws-send', { type: 'copy_text', text }),

  // Hotkey capture — in Electron we'll handle this differently
  capture_hotkey: (cb) => {
    ipcRenderer.invoke('capture-hotkey').then(chord => cb(chord));
  },

  // Signals (React connects to these for real-time events)
  state_changed: {
    connect: (cb) => signals.state_changed.connect(cb),
    disconnect: (cb) => signals.state_changed.disconnect(cb),
  },
  input_level: {
    connect: (cb) => signals.input_level.connect(cb),
    disconnect: (cb) => signals.input_level.disconnect(cb),
  },
  dictation_done: {
    connect: (cb) => signals.dictation_done.connect(cb),
    disconnect: (cb) => signals.dictation_done.disconnect(cb),
  },
  paused_changed: {
    connect: (cb) => signals.paused_changed.connect(cb),
    disconnect: (cb) => signals.paused_changed.disconnect(cb),
  },
  data_changed: {
    connect: (cb) => signals.data_changed.connect(cb),
    disconnect: (cb) => signals.data_changed.disconnect(cb),
  },
});
