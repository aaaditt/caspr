/**
 * ws-client.js — WebSocket client connecting to the Python backend.
 *
 * Manages the connection lifecycle, auto-reconnects, and provides a
 * request/response pattern with message IDs on top of the raw WebSocket.
 */

const WebSocket = require('ws');
const EventEmitter = require('events');

class WsClient extends EventEmitter {
  constructor(port = 18321) {
    super();
    this.url = `ws://127.0.0.1:${port}/ws`;
    this._ws = null;
    this._stopped = false;
    this._reconnectDelay = 1000;
    this._maxReconnectDelay = 8000;
    this._currentDelay = this._reconnectDelay;
    this._nextId = 1;
    this._pending = new Map(); // id → {resolve, reject, timer}
  }

  connect() {
    if (this._ws) return;
    this._stopped = false;

    console.log(`[ws] connecting to ${this.url}...`);
    this._ws = new WebSocket(this.url);

    this._ws.on('open', () => {
      console.log('[ws] connected');
      this._currentDelay = this._reconnectDelay; // reset backoff
      this.emit('connected');
    });

    this._ws.on('message', (data) => {
      try {
        const msg = JSON.parse(data.toString());
        // If it has an id, it's a response to a request
        if (msg.id && this._pending.has(msg.id)) {
          const { resolve, timer } = this._pending.get(msg.id);
          clearTimeout(timer);
          this._pending.delete(msg.id);
          resolve(msg);
        } else {
          // It's a pushed event
          this.emit('event', msg);
          this.emit(msg.type, msg);
        }
      } catch (err) {
        console.error('[ws] parse error:', err.message);
      }
    });

    this._ws.on('close', () => {
      console.log('[ws] disconnected');
      this._ws = null;
      this.emit('disconnected');
      this._scheduleReconnect();
    });

    this._ws.on('error', (err) => {
      // Errors are followed by 'close', so reconnect happens there
      if (err.code !== 'ECONNREFUSED') {
        console.error('[ws] error:', err.message);
      }
    });
  }

  disconnect() {
    this._stopped = true;
    this._pending.forEach(({ reject, timer }) => {
      clearTimeout(timer);
      reject(new Error('disconnected'));
    });
    this._pending.clear();
    if (this._ws) {
      this._ws.close();
      this._ws = null;
    }
  }

  /**
   * Send a fire-and-forget message (no response expected).
   */
  send(msg) {
    if (!this._ws || this._ws.readyState !== WebSocket.OPEN) return false;
    this._ws.send(JSON.stringify(msg));
    return true;
  }

  /**
   * Send a request and wait for the response (matched by message id).
   * Returns a Promise that resolves with the response message.
   */
  request(msg, timeoutMs = 5000) {
    return new Promise((resolve, reject) => {
      if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
        return reject(new Error('not connected'));
      }
      const id = this._nextId++;
      const timer = setTimeout(() => {
        this._pending.delete(id);
        reject(new Error(`request timeout: ${msg.type}`));
      }, timeoutMs);
      this._pending.set(id, { resolve, reject, timer });
      this._ws.send(JSON.stringify({ ...msg, id }));
    });
  }

  get connected() {
    return this._ws && this._ws.readyState === WebSocket.OPEN;
  }

  _scheduleReconnect() {
    if (this._stopped) return;
    console.log(`[ws] reconnecting in ${this._currentDelay}ms...`);
    setTimeout(() => {
      if (!this._stopped) this.connect();
    }, this._currentDelay);
    // Exponential backoff with cap
    this._currentDelay = Math.min(this._currentDelay * 1.5, this._maxReconnectDelay);
  }
}

module.exports = { WsClient };
