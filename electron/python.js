/**
 * python.js — Spawn and manage the Python backend as a child process.
 *
 * Starts `uv run caspr --server --port <port>` and monitors its lifecycle.
 * Auto-restarts on crash. Logs stdout/stderr to Electron's console.
 */

const { spawn } = require('child_process');
const path = require('path');
const EventEmitter = require('events');

class PythonBackend extends EventEmitter {
  constructor(port = 18321) {
    super();
    this.port = port;
    this._proc = null;
    this._restarting = false;
    this._stopped = false;
    this._restartDelay = 2000;
    // Resolve the project root (one level up from electron/)
    this._cwd = path.resolve(__dirname, '..');
  }

  start() {
    if (this._proc) return;
    this._stopped = false;

    const args = ['run', 'caspr', '--server', '--port', String(this.port)];
    console.log(`[python] spawning: uv ${args.join(' ')} in ${this._cwd}`);

    this._proc = spawn('uv', args, {
      cwd: this._cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      // On Windows, don't open a visible console window
      windowsHide: true,
    });

    this._proc.stdout.on('data', (data) => {
      const lines = data.toString().trim();
      if (lines) console.log(`[python] ${lines}`);
    });

    this._proc.stderr.on('data', (data) => {
      const lines = data.toString().trim();
      if (lines) console.error(`[python] ${lines}`);
    });

    this._proc.on('error', (err) => {
      console.error('[python] spawn error:', err.message);
      this.emit('error', err);
    });

    this._proc.on('exit', (code, signal) => {
      console.log(`[python] exited: code=${code} signal=${signal}`);
      this._proc = null;
      this.emit('exit', code, signal);

      if (!this._stopped) {
        console.log(`[python] restarting in ${this._restartDelay}ms...`);
        setTimeout(() => {
          if (!this._stopped) this.start();
        }, this._restartDelay);
      }
    });

    this.emit('started');
  }

  stop() {
    this._stopped = true;
    if (!this._proc) return;

    console.log('[python] stopping...');
    // On Windows, tree-kill is more reliable but for now just kill the process
    this._proc.kill('SIGTERM');
    // Force kill after 3 seconds if it hasn't exited
    setTimeout(() => {
      if (this._proc) {
        console.log('[python] force killing...');
        this._proc.kill('SIGKILL');
      }
    }, 3000);
  }

  get running() {
    return this._proc !== null;
  }
}

module.exports = { PythonBackend };
