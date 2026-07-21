# caspr-flow

Hold a key, speak, release — polished text appears at your cursor, in any Windows app.

A personal Wispr Flow–style dictation tool: local Whisper for speech-to-text
(your audio never leaves the machine), a fast LLM pass for cleanup, and
clipboard-swap paste into whatever has focus.

## Status

Milestone 1 (core loop) — in progress. See
[docs/superpowers/specs/2026-07-15-caspr-flow-design.md](docs/superpowers/specs/2026-07-15-caspr-flow-design.md)
for the full design.

## Quick start

```powershell
uv sync --extra cuda
uv run caspr --install-launcher   # once: puts 'caspr' on PATH
caspr                             # launches detached (tray dot appears)
caspr --startup on                # optional: always running after login
```

Hold **right Ctrl** to talk; release to type into the focused app. After each
dictation a pill lingers at the bottom of the screen — click it to correct
words, right-click a red word to add it to your dictionary or create an
"always replace" rule. Tray → History & dictionary reviews everything.

`uv run caspr` runs attached to the terminal with console logs (dev mode).

## STT engines

Two engines, routed by Settings → Transcription → Engine:

- **Parakeet** (nvidia/parakeet-tdt-0.6b-v2 via onnx-asr) — English only, ~5x
  faster than whisper-large-v3-turbo on this machine (≈0.3s vs ≈1.8s per clip)
  with better English accuracy (Open ASR leaderboard 6.05 vs ~7.8 WER). Runs
  on CPU, leaving the GPU free. Dictionary hints don't apply on this path
  (no prompt biasing); replacement rules still do.
- **Whisper** (faster-whisper) — all languages incl. Hindi and auto-detect.

**Auto** (default) uses Parakeet when Language is pinned to English, Whisper
otherwise. First Parakeet use downloads ~1.2 GB from Hugging Face.

Note: better Hindi exists (shunyalabs/pingala-v1-universal beats
whisper-large-v3 on the Vaani benchmark) but the repo is gated — request
access on Hugging Face if wanted.

## Desktop App (Electron)

The main window is an Electron app (`electron/`) that hosts the React + Tailwind
UI (`webui/`). The Python backend runs as a child process, communicating over a
local WebSocket. The pill overlay stays as a native Qt widget for reliable
always-on-top behavior.

### Quick launch

```powershell
# First time setup
uv sync --extra cuda                # Python deps
cd electron && npm install && cd .. # Electron deps

# Run the app
cd electron && npm start            # or: npx electron .
```

Electron spawns `uv run caspr --server` automatically — no need to start
Python separately.

### Development mode

```powershell
cd webui && npm run dev             # Vite dev server with hot reload on :5173
cd electron
$env:CASPR_UI_DEV = '1'
npm start                           # Electron loads localhost:5173 instead of dist
```

### Legacy Qt mode

The old QtWebEngine path still works for quick testing without Node:

```powershell
uv run caspr                        # Opens the Qt-hosted window
```

### Server mode (headless)

Run just the Python backend with the pill overlay and WebSocket server:

```powershell
uv run caspr --server               # ws://127.0.0.1:18321/ws
uv run caspr --server --port 9999   # custom port
```

After UI changes, rebuild and commit the bundle: `cd webui && npm run build`.
