# caspr-flow

Hold a key, speak, release — polished text appears at your cursor, in any Windows app.

A personal [Wispr Flow](https://wispr.com)–style dictation tool: local Whisper
for speech-to-text (your audio never leaves the machine), a fast LLM pass for
cleanup via Groq, and keystroke/clipboard injection into whatever has focus.

## Features

- **Push-to-talk** — hold your hotkey (default: Ctrl+Win), speak, release.
  Text is typed into whatever window has focus.
- **AI cleanup** — optional Groq LLM pass that fixes grammar, punctuation,
  casing, and filler words. Falls back to raw text if Groq is unreachable.
- **Tone profiles** — per-app writing styles (casual for Slack, formal for
  email). Configurable in Settings.
- **Hands-free mode** — double-tap the hotkey to toggle continuous recording.
- **Pill overlay** — floating transcript pill that lingers after each dictation.
  Click to correct words, right-click a red word to add it to your dictionary
  or create an "always replace" rule.
- **Two STT engines** — Whisper (all languages) and Parakeet (English, ~5× faster).
- **Custom dictionary** — teach it names, jargon, acronyms. Terms survive updates.
- **Settings UI** — full React settings page for model, device, engine,
  language, hotkeys, mic selection, and more.

## Requirements

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10/11 (uses `SendInput` for keystroke injection + `keyboard` library for global hotkeys) |
| **Python** | 3.11+ |
| **uv** | [Install uv](https://docs.astral.sh/uv/getting-started/installation/) — manages Python deps + venv |
| **Node.js** | 18+ (for the Electron desktop app and UI development) |
| **GPU (optional)** | NVIDIA GPU with CUDA for faster transcription. CPU-only works but is slower. |
| **Groq API key (optional)** | Free at [console.groq.com](https://console.groq.com) — enables AI cleanup. Without it, raw transcripts are injected directly. |

## Disk space

| Component | Size | Notes |
|-----------|------|-------|
| Source code | ~0.5 MB | What you clone from the repo |
| Python venv (`.venv/`) | ~3 GB | PySide6, faster-whisper, PyTorch, etc. Add ~1.5 GB with `--extra cuda` for NVIDIA GPU libs |
| Electron deps (`electron/node_modules/`) | ~300 MB | Chromium runtime |
| WebUI deps (`webui/node_modules/`) | ~110 MB | Only needed for UI development |
| Whisper model (auto-downloaded) | 0.3–3 GB | `small` = ~0.5 GB, `large-v3-turbo` = ~3 GB. Stored in `~/.cache/huggingface/` |
| Parakeet model (auto-downloaded) | ~1.2 GB | Downloaded on first use if engine is set to Parakeet or Auto+English |
| **Total (typical)** | **~5–8 GB** | With `small` Whisper model + CUDA + Electron |

## Quick start

```powershell
# 1. Clone
git clone https://github.com/aaaditt/caspr.git
cd caspr

# 2. Install Python dependencies
uv sync                            # CPU-only
uv sync --extra cuda               # with NVIDIA GPU acceleration

# 3. Install Electron dependencies
cd electron && npm install && cd ..

# 4. Launch the app
cd electron && npm start
```

Electron spawns the Python backend automatically — no need to start it separately.

On first launch, Whisper downloads its model weights (~0.5 GB for `small`). This
is a one-time download stored in `~/.cache/huggingface/`.

### Optional setup

```powershell
# Put 'caspr' on your PATH (one-time)
uv run caspr --install-launcher

# Auto-start on login
caspr --startup on

# Set your Groq API key for AI cleanup (in Settings UI, or manually):
# Edit %APPDATA%\caspr-flow\config.json → "groq_api_key": "gsk_..."
```

## Usage

1. **Hold your hotkey** (default: **Ctrl+Win**) and speak
2. **Release** — text appears at your cursor
3. A **pill overlay** lingers at the bottom of the screen:
   - Click it to open the correction popup
   - Right-click a red (flagged) word to add it to your dictionary or create a replacement rule
4. **System tray** — right-click the tray icon to show the window, pause dictation, or quit
5. **Settings** — configure model, engine, language, hotkeys, mic, tone profiles, and more

### Hands-free mode

Double-tap your hotkey to toggle continuous recording. The app listens and
transcribes until you double-tap again or press the cancel hotkey.

### Hotkeys

| Action | Default | Configurable |
|--------|---------|:------------:|
| Push-to-talk | Ctrl+Win | ✅ (Settings → Hotkey) |
| Toggle dictation | — | ✅ |
| Cancel dictation | — | ✅ |
| Mute mic | — | ✅ |
| Open history | — | ✅ |

## Configuration

Config is stored at `%APPDATA%\caspr-flow\config.json`. All settings are also
editable through the Settings page in the UI.

| Key | Default | Description |
|-----|---------|-------------|
| `hotkey` | `"ctrl+windows"` | Push-to-talk chord |
| `model` | `"small"` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3-turbo` |
| `device` | `"auto"` | `auto`, `cuda`, or `cpu` |
| `engine` | `"auto"` | `auto`, `whisper`, or `parakeet` |
| `language` | `null` | Pin to a language (e.g. `"en"`) or `null` for auto-detect |
| `injection` | `"type"` | `"type"` (SendInput keystrokes) or `"clipboard"` (Ctrl+V paste) |
| `cleanup_enabled` | `true` | Enable AI cleanup via Groq |
| `groq_api_key` | `""` | Groq API key (blank = raw mode, no cleanup) |
| `groq_model` | `"llama-3.1-8b-instant"` | Groq model for cleanup |
| `tone_default` | `"balanced"` | Default tone: `balanced`, `casual`, `formal`, `terse` |
| `tone_profiles` | `{}` | Per-app tones, e.g. `{"slack.exe": "casual", "outlook.exe": "formal"}` |
| `handsfree_double_tap` | `true` | Enable double-tap to toggle hands-free mode |
| `sound_cues` | `true` | Play soft ticks on record start/stop |
| `pill_linger_s` | `6.0` | Seconds the pill stays visible (0 = disabled) |

## STT engines

Two engines, routed by Settings → Transcription → Engine:

- **Parakeet** (nvidia/parakeet-tdt-0.6b-v2 via onnx-asr) — English only, ~5×
  faster than whisper-large-v3-turbo (≈0.3 s vs ≈1.8 s per clip) with better
  English accuracy (Open ASR leaderboard 6.05 vs ~7.8 WER). Runs on CPU,
  leaving the GPU free. Dictionary hints don't apply on this path (no prompt
  biasing); replacement rules still do.
- **Whisper** (faster-whisper) — all languages incl. Hindi and auto-detect.

**Auto** (default) uses Parakeet when Language is pinned to English, Whisper
otherwise. First Parakeet use downloads ~1.2 GB from Hugging Face.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Electron (electron/main.js)                │
│  ├─ BrowserWindow → React UI (webui/dist)   │
│  ├─ System tray (show / pause / quit)       │
│  ├─ Global shortcuts (action hotkeys)       │
│  └─ Spawns Python as child process          │
│       ↕ WebSocket ws://127.0.0.1:18321/ws   │
├─────────────────────────────────────────────┤
│  Python backend (caspr --server)            │
│  ├─ AppController (state machine)           │
│  ├─ STT (Whisper / Parakeet)                │
│  ├─ Audio recording (sounddevice)           │
│  ├─ Text injection (SendInput / clipboard)  │
│  ├─ AI cleanup (Groq)                       │
│  ├─ Pill overlay (Qt widget, always-on-top) │
│  └─ WebSocket server (aiohttp)              │
└─────────────────────────────────────────────┘
```

## Project structure

```
caspr-flow/
├── caspr/               # Python backend
│   ├── __main__.py      # CLI entry point
│   ├── app.py           # AppController state machine
│   ├── server.py        # WebSocket server for Electron
│   ├── config.py        # Config dataclass + JSON persistence
│   ├── stt.py           # Whisper transcription
│   ├── stt_router.py    # Engine auto-routing (Whisper vs Parakeet)
│   ├── hotkeys.py       # Push-to-talk keyboard hooks
│   ├── inject.py        # Text injection into focused window
│   ├── cleanup.py       # AI cleanup via Groq
│   ├── sounds.py        # Sound cue synthesis
│   └── ui/              # Qt widgets (pill overlay, correction popup)
├── electron/            # Electron desktop shell
│   ├── main.js          # Main process
│   ├── preload.js       # Secure bridge for renderer
│   ├── python.js        # Python child process manager
│   ├── ws-client.js     # WebSocket client
│   ├── tray.js          # System tray
│   └── hotkeys.js       # Global shortcut manager
├── webui/               # React + Tailwind UI
│   ├── src/             # TypeScript source
│   └── dist/            # Pre-built bundle (committed)
├── tests/               # Pytest test suite (84 tests)
├── docs/                # Design specs and notes
├── scripts/             # Utility scripts
└── pyproject.toml       # Python project config
```

## Desktop app (Electron)

The main window is an Electron app (`electron/`) that hosts the React + Tailwind
UI (`webui/`). The Python backend runs as a child process, communicating over a
local WebSocket. The pill overlay stays as a native Qt widget for reliable
always-on-top behavior.

### Development mode

```powershell
# Terminal 1: Vite dev server with hot reload
cd webui && npm run dev

# Terminal 2: Electron loading localhost:5173
cd electron
$env:CASPR_UI_DEV = '1'
npm start
```

### Legacy Qt mode

The old QtWebEngine path still works for quick testing without Node/Electron:

```powershell
uv run caspr                        # Opens the Qt-hosted window
```

### Server mode (headless)

Run just the Python backend + pill overlay + WebSocket server:

```powershell
uv run caspr --server               # ws://127.0.0.1:18321/ws
uv run caspr --server --port 9999   # custom port
```

### Rebuilding the UI

After UI changes, rebuild and commit the bundle:

```powershell
cd webui && npm run build
```

The built bundle in `webui/dist/` is committed to the repo, so cloning the repo
and running `cd electron && npm start` works without a separate UI build step.

## Running tests

```powershell
uv run pytest                       # all 84 tests
uv run pytest -x -v                 # stop on first failure, verbose
uv run pytest -m "not slow"         # skip model-download tests
```

## License

Private / personal project.
