# Velvet Premium Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Qt-widget main window with a frameless, website-grade React app (Velvet design) rendered by QtWebEngine inside the existing Python process.

**Architecture:** `caspr/ui/shell.py` (frameless Qt host + QWebEngineView + DWM rounded corners) exposes `caspr/ui/bridge.py` (`Bridge(QObject)`) over QWebChannel to a Vite-built React SPA in `webui/`. Engine, hotkeys, tray, pill stay Qt; remaining Qt surfaces get the Velvet palette.

**Tech Stack:** PySide6 QtWebEngine/QtWebChannel · Vite + React 18 + TypeScript · Tailwind CSS v4 · `motion` · `qwebchannel` (npm) · @fontsource/inter + @fontsource/instrument-serif

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-18-premium-webui-design.md` — palette/typography values are normative.
- Every task ends with commit + push to `origin main` (standing rule).
- `webui/dist/` is committed; `uv run caspr` must work without Node.
- No network fetches at runtime (fonts bundled).
- `--wav` debug path must never construct the web shell.
- Fast tests (`uv run pytest -m "not slow"`) + `uv run ruff check .` green before every commit.
- Velvet tokens: bg `#151110`, surface `#1c1715`, raised `#241d1a`, hairline `#2a221d`, cream `#f6efe7`, muted `#9c8f85`, coral `#ff8a65`, amber `#ffb74d`. STATE_COLORS: loading `#9c8f85`, idle `#ffb74d`, recording `#ff5c49`, processing `#e8a13c`, error `#e05252`, paused `#b8a06a`.

---

### Task 1: Velvet React shell + frameless host window

**Files:**
- Create: `webui/` (Vite scaffold: `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/index.css`)
- Create: `webui/src/components/TitleBar.tsx`, `Sidebar.tsx`, `ResizeEdges.tsx`, `Card.tsx`, `Waveform.tsx`
- Create: `webui/src/pages/Home.tsx` (mock data), stubs `History.tsx`, `Dictionary.tsx`, `Settings.tsx`
- Create: `caspr/ui/shell.py`
- Modify: `caspr/__main__.py` (Shell replaces MainWindow; keep MainWindow import gone at Task 5)
- Commit: `webui/dist/`

**Interfaces:**
- Produces: `Shell(controller)` with `.surface()`, `closeEvent→hide`, signals `hotkey_changed(str)`, `capture_active(bool)` (relocated from MainWindow so `__main__.py` wiring is unchanged in shape).
- Produces (JS): `window.caspr` bridge object placeholder — Task 1 renders with mock data when bridge absent, so `npm run dev` works in a plain browser.

- [ ] **Step 1: Preflight Node** — `node --version && npm --version` (need Node ≥ 18). If missing, stop and ask Aadit to install Node LTS.
- [ ] **Step 2: Scaffold** —
  `cd webui && npm create vite@latest . -- --template react-ts && npm i && npm i tailwindcss @tailwindcss/vite motion qwebchannel @fontsource/inter @fontsource-variable/instrument-serif? (use @fontsource/instrument-serif) `
  `vite.config.ts`: `base: './'` (file:// asset paths), tailwind plugin.
- [ ] **Step 3: Tokens** — `src/index.css`: `@import "tailwindcss";` + `@theme` block mapping the Velvet tokens (colors above, `--font-display: 'Instrument Serif', Georgia, serif`, `--font-sans: 'Inter', 'Segoe UI', sans-serif`) + font imports + base styles (bg, selection color, scrollbar styling).
- [ ] **Step 4: Shell components** — TitleBar (drag region `onMouseDown→bridge.win_drag()`, min/close buttons right-aligned, brand left), Sidebar (serif italic "caspr" brand + 4 nav items with SVG glyphs, active pill, hover states), ResizeEdges (8 absolutely-positioned 6px strips calling `bridge.win_resize(edge)` on mousedown), Card (surface + hairline + radius 18 + hover lift via motion), Waveform (28 bars, props `levels: number[]`, `mode`), Home page mirroring the approved mockup with mock data.
- [ ] **Step 5: Bridge stub** — `src/bridge.ts`: typed `CasprApi` interface; `initBridge(): Promise<CasprApi | null>` — resolves null outside Qt (mock mode). All calls no-op in mock mode.
- [ ] **Step 6: Build** — `npm run build` → verify `webui/dist/index.html` + assets exist.
- [ ] **Step 7: shell.py** —
```python
class Shell(QWidget):
    hotkey_changed = Signal(str)
    capture_active = Signal(bool)
    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.resize(940, 600); self.setWindowTitle("caspr")
        view = QWebEngineView(self)                      # fills via QVBoxLayout margin 0
        view.page().setBackgroundColor(QColor("#151110"))
        self._round_corners()                            # DWMWA 33 → 2, try/except OSError
        url = os.environ.get("CASPR_UI_DEV") and QUrl("http://localhost:5173") \
              or QUrl.fromLocalFile(str(Path(__file__).parents[2] / "webui/dist/index.html"))
        view.load(url)
    def surface(self): show/raise/activate
    def closeEvent(self, e): e.ignore(); self.hide()
```
  (Bridge registered in Task 2 — Task 1 window just renders the page.)
- [ ] **Step 8: Wire `__main__.py`** — swap `MainWindow(controller)` → `Shell(controller)`; existing `hotkey_changed`/`capture_active`/tray `on_open`/QLocalServer wiring keeps working because signal names match. MainWindow stays importable (History fallback) until Task 5.
- [ ] **Step 9: Verify** — `uv run caspr`: frameless Velvet window, rounded corners, drag by title bar, minimize + close-to-tray buttons work (buttons call bridge → absent in Task 1, so wire min/close via a temporary `QShortcut`? NO — instead register a minimal `WindowControls` QObject on the channel already in Task 1 with `win_minimize/win_close/win_drag/win_resize` so chrome is functional immediately).
- [ ] **Step 10: Tests + commit** — `uv run pytest -m "not slow"`, `ruff check .`, commit `Velvet React shell in a frameless QtWebEngine window` + push.

### Task 2: Live bridge + real Home page

**Files:**
- Create: `caspr/ui/bridge.py`, `tests/test_bridge_data.py`
- Modify: `caspr/ui/shell.py` (register full bridge), `webui/src/bridge.ts`, `state.tsx`, `pages/Home.tsx`, `components/Waveform.tsx`

**Interfaces:**
- Produces (Python `Bridge(QObject)`, channel name `"caspr"`):
  - Signals: `state_changed(str,str)`, `input_level(float)`, `dictation_done(str,'QVariantList')`, `paused_changed(bool)`
  - Slots: `get_bootstrap()->'QVariantMap'`, `win_minimize()`, `win_close()`, `win_drag()`, `win_resize(str)` (absorbs Task 1's WindowControls)
- Produces (pure, tested): `caspr/ui/bridge_data.py:: bootstrap(controller) -> dict`, `entry_dict(entry, cfg) -> dict` (`{id, ts, text, spans:[[s,e],…]}`)
- Consumes: `AppController` signals; `history.stats()/recent()`; `flag_unknown_words`.

- [ ] Failing tests for `entry_dict` (spans as lists, JSON-serializable via `json.dumps`) and `bootstrap` keys (`state, paused, hotkey, hotkey_pretty, model, device, language, injection, pill_linger_s, sound_cues, input_device, mics, startup, stats{today,words,avg_s}, recent[]`) → implement → pass.
- [ ] Bridge forwards controller signals (connect in `__init__`); `get_bootstrap` returns `bootstrap(self._controller)`.
- [ ] React: `state.tsx` context — `useCaspr()` hook exposing bootstrap + live state + `levels` ring buffer (28, updated on `input_level`, rAF decay identical feel to Qt pill: rise instant, fall ×0.88/frame).
- [ ] Home real: greeting from local clock, status card (state→copy map, pulsing dot color by state, waveform live in recording, shimmer in processing), 3 stat cards (animated count-up via motion), Recent 5 with client-side `relTime(ts)` ticking every 30 s (port `caspr/timefmt.py` semantics to `src/lib/reltime.ts`).
- [ ] Verify live: dictate → dot goes coral, waveform moves, stats/recent update on `dictation_done`.
- [ ] `npm run build`, tests, ruff, commit `Live bridge: real Home with waveform, stats, recent` + push.

### Task 3: History + Dictionary pages

**Files:**
- Modify: `caspr/ui/bridge.py` (+slots), `webui/src/pages/History.tsx`, `Dictionary.tsx`
- Test: extend `tests/test_bridge_data.py`

**Interfaces:**
- Slots: `get_history(str query)->'QVariantList'` (search when non-empty else recent(200)), `delete_entry(int)`, `copy_text(str)` (QGuiApplication clipboard), `correct(str)` (opens `CorrectionPopup(controller, text)`; refresh pushed via existing `dictation_done`? No — after popup closes emit new signal `data_changed()` consumed by React to refetch), `get_dictionary()->'QVariantMap'` (`{terms:[…], rules:[{wrong,right}]}`), `learn_term(str)`, `forget_term(str)`, `forget_rule(str)`.
- Signal: `data_changed()` — emitted after correct/learn/forget/delete so pages refetch.

- [ ] History page: search field (debounced 150 ms), rows (relTime muted + flagged spans in coral underline), hover actions (copy / correct / delete) with motion, empty states ("Nothing here yet — hold {hotkey_pretty} and speak." / "No matches."), delete with exit animation.
- [ ] Dictionary page: two columns, add-term input (Enter), remove on hover, rules list `wrong → right`, empty states per spec copy (reuse current Qt copy).
- [ ] Tests: dictionary payload shape; history query passthrough (fake controller).
- [ ] Build, verify in app, tests, ruff, commit `History and Dictionary pages over the bridge` + push.

### Task 4: Settings page (hotkey capture, mic picker, hot-reload)

**Files:**
- Modify: `caspr/ui/bridge.py`, `webui/src/pages/Settings.tsx`
- Test: extend `tests/test_bridge_data.py`

**Interfaces:**
- Slots: `set_setting(str key, 'QVariant' value)` — routing: `model|device` → `_save` + `controller.reload_model()`; `input_device` → `_save` + `controller.set_input_device()`; `hotkey` → `_save` + emit `hotkey_changed(chord)` (Shell re-emits, `__main__` re-arms); `language|injection|pill_linger_s|sound_cues` → `_save` only. `capture_hotkey()->'QVariant'` — emits `capture_active(True)`, opens `HotkeyCaptureDialog`, returns chord or `None`, emits `capture_active(False)` in finally, saves via same path as `set_setting('hotkey',…)` when accepted. `set_startup(bool)`.
- `_save` = mutate `controller.cfg` + `save_config` (port of MainWindow._save without widget bits — lives in bridge).

- [ ] Settings page: sectioned Velvet cards (Dictation / Transcription / Output / Feedback / System) — custom styled select, toggle switch, slider (pill linger), hotkey row (pretty chord + "Change…" button → `capture_hotkey()` promise + presets menu), mic select from bootstrap `mics`, "applies immediately" notes.
- [ ] Test: `set_setting` routing with a fake controller (records reload/set_input_device calls; asserts cfg mutation+persist).
- [ ] Build, verify: model switch hot-reloads (status → loading), hotkey capture works with PTT suspended, mic switch takes on next dictation. Tests, ruff, commit `Settings page: capture, mic picker, hot-reload over the bridge` + push.

### Task 5: Velvet-ify remaining Qt + retire dead code

**Files:**
- Modify: `caspr/ui/style.py` (Velvet palette + STATE_COLORS per Global Constraints; QSS now only serves correct.py + hotkey_capture.py), `caspr/ui/icons.py` (coral→amber gradient mic on espresso), `caspr/ui/overlay.py` (bars = QLinearGradient coral→amber, body `#1c1715` α244, warm border), `caspr/ui/tray.py` (no change beyond icons), `caspr/ui/correct.py` (verify QSS still covers it)
- Delete: `caspr/ui/main_window.py`
- Modify: `tests/test_style.py` (colors updated), `caspr/__main__.py` (drop any MainWindow remnants)

- [ ] Palette swap; repaint icons; pill gradient; run app — pill/tray/popup all warm, no cyan anywhere.
- [ ] Delete `main_window.py`; grep for imports (`Grep: main_window`) → none.
- [ ] Tests, ruff, commit `Velvet across Qt surfaces; retire widget main window` + push.

### Task 6: Motion & polish pass

**Files:** `webui/src/**` only (+ `README.md`)

- [ ] Page transitions (`AnimatePresence`, 180 ms slide+fade), staggered card entrance on first open, button/row hover micro-interactions, focus rings (cream, 2px), `prefers-reduced-motion` guard (motion's `useReducedMotion`), title-bar double-click → maximize? NO (fixed premium feel — skip, YAGNI).
- [ ] README: webui section (`npm run dev` + `CASPR_UI_DEV=1 uv run caspr`, `npm run build` before committing UI changes).
- [ ] Build, verify, tests, ruff, commit `Motion polish + webui docs` + push.

## Self-Review Notes

- Spec coverage: every spec bullet maps to a task (bridge contract→2-4, frameless→1, fonts→1, Qt reskin→5, motion→6, README→6). ✓
- Types consistent: `Bridge` slot names identical across Tasks 2-4; `data_changed` introduced Task 3 and only used from Task 3 on. ✓
- The Task 1 "WindowControls" note resolves into the same object that becomes the full Bridge in Task 2 (same channel name `"caspr"`), so the JS side never changes its lookup. ✓
