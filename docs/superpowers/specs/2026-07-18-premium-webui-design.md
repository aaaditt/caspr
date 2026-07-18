# caspr premium web UI — "Velvet" (approved 2026-07-18)

Aadit's verdict on the Qt-widget UI: functional but mid. Goal: a genuinely premium
main window — website-grade rendering, typography, and motion — without touching
the dictation engine. Direction chosen from three mockups: **C — Velvet** (warm
luxury: espresso surfaces, cream text, coral→amber accents, serif display).
Architecture chosen: **React inside the app**. Chrome: **frameless custom**.

## Architecture

One Python process, as today. The main window becomes a frameless Qt shell
hosting **QtWebEngine** (ships with installed PySide6), rendering a
**React + TypeScript + Tailwind + Motion** SPA. Engine, hotkeys, tray, and the
pill overlay stay Python/Qt.

```
QApplication
├── AppController (unchanged: states, executor, signals)
├── Pill (Qt, re-skinned Velvet)          ├── Tray (Qt, Velvet icons)
└── Shell (frameless QWidget)
    └── QWebEngineView ── QWebChannel ── Bridge(QObject)
                                └── React app (webui/dist)
```

### Bridge contract (QWebChannel)

Python → JS signals:
- `stateChanged(state, detail)`, `inputLevel(float)` (~10 Hz, drives Home waveform),
  `dictationDone(text, spans)`, `pausedChanged(bool)`

JS → Python slots (JSON-serializable returns):
- `get_bootstrap()` — config, stats, recent dictations (with flag spans), state,
  paused, mic list, startup flag, pretty hotkey
- `get_history(query)` / `delete_entry(id)` / `copy_text(text)` / `correct(text)`
  (opens Qt CorrectionPopup)
- `get_dictionary()` / `learn_term` / `forget_term` / `forget_rule`
- `set_setting(key, value)` — model/device route through `reload_model()`,
  input_device through `set_input_device()`, hotkey re-arms live
- `capture_hotkey()` — opens the Qt HotkeyCaptureDialog; PTT suspended around it
  (same capture_active contract as today, relocated to the Bridge)
- `toggle_pause()`, `set_startup(on)`
- Window: `win_minimize()`, `win_close()` (hide to tray), `win_drag()`
  (`startSystemMove`), `win_resize(edge)` (`startSystemResize`)

### Frameless chrome

- `FramelessWindowHint`; Windows 11 native rounded corners + shadow via
  `DwmSetWindowAttribute(DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)` (ctypes,
  guarded try/except — Win10 falls back to square).
- Drag: title-bar region in React calls `win_drag()` → `startSystemMove()`
  (native move; Aero snap keeps working).
- Resize: 6 px edge hover zones in React call `win_resize(edge)`.
- Custom window buttons (minimize, close-to-tray) in the React title bar.
- First-paint flash prevented with `page().setBackgroundColor(espresso)`.

## Velvet design language

- Background `#151110`, surface `#1c1715`, raised `#241d1a`, hairline `#2a221d`
- Text cream `#f6efe7`, muted `#9c8f85`
- Accent gradient coral `#ff8a65` → amber `#ffb74d`; glows at low alpha
- Display type: **Instrument Serif** (italic accents); UI type: **Inter**
  — both bundled locally via @fontsource, no network fetches
- Motion: spring page transitions, hover lifts, animated waveform, pulsing
  status dot; respects `prefers-reduced-motion`
- STATE_COLORS re-tuned warm: loading `#9c8f85`, idle `#ffb74d`,
  recording `#ff5c49`, processing `#e8a13c`, error `#e05252`, paused `#b8a06a`

Remaining Qt surfaces (pill, tray/app icons, correction popup, capture dialog)
repainted to the same palette in `style.py`/`icons.py` so nothing clashes.

## Build & repo layout

- `webui/` — Vite + React + TS + Tailwind + motion; `webui/dist/` **committed**
  so `uv run caspr` works without Node. qwebchannel.js copied into the bundle.
- Dev loop: `CASPR_UI_DEV=1` env → shell loads `http://localhost:5173` (Vite HMR)
  instead of `dist/index.html`.
- `caspr/ui/shell.py` replaces `main_window.py` (Qt pages retired at milestone 5).

## Milestones (commit + push each)

1. Scaffold webui; Velvet static shell (title bar, sidebar, Home with mock
   data); frameless Qt host loading the bundle.
2. Bridge live: bootstrap + state/level signals; Home real (status, stats,
   recent, waveform).
3. History (search/copy/delete/correct) + Dictionary pages.
4. Settings: all fields, hotkey capture via Qt dialog, mic picker, hot-reload.
5. Velvet-ify pill/tray/icons/dialogs; delete dead Qt pages.
6. Motion & polish pass; README note on webui build.

## Risks

- QtWebEngine RAM (~150–250 MB with window open) — acceptable; lazy view
  teardown on hide is a noted future optimization, not in scope.
- WebChannel throughput at 10 Hz inputLevel — trivial.
- Frameless resize is hand-rolled — keep zones thin, test snap + multi-monitor.
- `--wav` debug path must never construct the web shell (already conditional).

Out of scope: onboarding wizard, web-rendered pill, light theme.
