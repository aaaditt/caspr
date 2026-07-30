# Persistent Mini-Bar Pill Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the floating recording pill (`caspr/ui/overlay.py`) always visible as a small mini-bar when idle, expanding into today's oval while recording; add a mouse click/hold gesture to start and stop dictation from it; make the waveform noticeably more reactive to voice; add a Settings toggle to turn the always-on bar off.

**Architecture:** One `Pill` QWidget grows a third render mode (`idle`, alongside the existing `live`/`label`), resizing and repositioning itself bottom-anchored between modes. A new small pure state-machine class, `ClickHoldGesture` (same style as the existing `GestureInterpreter`), turns raw mouse press/release timestamps into hold-to-dictate or click-to-toggle behavior via two new `AppController` entry points that bypass the keyboard's gesture system entirely.

**Tech Stack:** PySide6 (`QPainter`/`QWidget`) for the pill; the same Python dataclass config + React/Tailwind Settings pattern used throughout the app.

**Reference doc:** `docs/superpowers/specs/2026-07-30-persistent-pill-widget-design.md` (approved design).

## Global Constraints

- **Mouse gesture behavior** (exact, confirmed by Aadit): hold ≥0.25s then release → dictate while held, stop on release (same feel as the keyboard). Quick press+release → starts recording and leaves it running until the *next* mouse press (of any length) stops it. **No** double-click-for-hands-free via mouse — that stays keyboard-only.
- **Mouse input never touches the keyboard's `GestureInterpreter`** — a dedicated `ClickHoldGesture` instance, and dedicated `AppController.on_mouse_press`/`on_mouse_release` entry points that call the plain hold primitives (`_begin_recording`/`_commit_recording`) directly, no gesture branching.
- **New config field:** `pill_always_visible: bool = True` — Settings toggle "Always show the recording bar", default on.
- **Sensitivity fix values** (from the spec, starting points — tune live if needed, do not treat as immovable): `meter_level()` gains `** 0.5` power-law compression on top of its existing linear scaling; `Waveform.GAIN` drops from `2.2` to `1.3`; `Waveform._tick()`'s fall-off multiplier rises from `0.35` to `0.55`.
- **Compactness:** `Pill`'s live/label content margins shrink from `(22, 10, 22, 10)` to `(20, 6, 20, 6)` (the `_SHADOW` inset added to each is unchanged).
- **Idle mini-bar dimensions:** 56px wide (64px on hover), 5px tall, rounded, `muted`-colored at ~55% opacity (brightens toward `FG`/~85% on hover), positioned 8px above the screen's bottom edge (vs. the oval's existing 16px gap).
- **No change to the mic glyph icon**, no hands-free-via-mouse, no changes to `pill_linger_s`/transcript-label/correction-dialog behavior beyond returning to idle instead of hiding — see the spec's Non-goals.
- **No automated Qt widget test infra exists in this repo** (established pattern) — `overlay.py` changes are verified by a manual sanity-check script plus live testing, not pytest.

---

### Task 1: Compress `meter_level()` so quiet speech reads more visibly

**Files:**
- Modify: `caspr/audio.py:39-44` (the `meter_level` function)
- Test: `tests/test_audio_level.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `meter_level(block: np.ndarray) -> float` — same signature, same 0..1 range, same callers (`Recorder`'s audio callback → `AppController.input_level` → both `Pill.set_level` and the webui Home page's live meter).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_audio_level.py`:

```python
def test_quiet_signal_boosted_above_old_linear_value():
    t = np.linspace(0, 1, 16000, dtype=np.float32)
    quiet = (np.sin(2 * np.pi * 440 * t) * 0.05).astype(np.float32)
    old_linear_level = min(
        1.0, float(np.sqrt(np.mean(np.square(quiet, dtype=np.float64)))) * np.sqrt(2.0)
    )
    assert meter_level(quiet) > old_linear_level
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audio_level.py::test_quiet_signal_boosted_above_old_linear_value -v`
Expected: FAIL — before the fix, `meter_level(quiet)` computes exactly `old_linear_level`, so `>` is false.

- [ ] **Step 3: Add power-law compression**

In `caspr/audio.py`, replace:

```python
def meter_level(block: np.ndarray) -> float:
    """Map an audio block to a 0..1 level for the UI meter (full-scale sine ≈ 1.0)."""
    if block.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
    return min(1.0, rms * np.sqrt(2.0))
```

with:

```python
def meter_level(block: np.ndarray) -> float:
    """Map an audio block to a 0..1 level for the UI meter (full-scale sine ≈ 1.0).

    Power-law compressed (sqrt) so normal speaking volume -- quiet relative
    to full-scale -- still visibly moves the meter, while loud input still
    caps at 1.0. Feeds both the pill's waveform and the webui's live meter.
    """
    if block.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
    level = min(1.0, rms * np.sqrt(2.0))
    return level ** 0.5
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audio_level.py -v`
Expected: all PASS, including the 4 pre-existing tests (silence stays 0.0; full-scale sine stays >0.95; clipped input stays capped at 1.0; quiet-vs-loud ordering is preserved — verify this by reading the output, not just trusting green).

- [ ] **Step 5: Commit**

```bash
git add caspr/audio.py tests/test_audio_level.py
git commit -m "feat(pill): compress meter_level so quiet speech reads more visibly"
```

---

### Task 2: More reactive waveform, more compact oval

**Files:**
- Modify: `caspr/ui/overlay.py` (the `Waveform.GAIN` constant, `Waveform._tick`'s fall-off, and `Pill.__init__`'s content margins)

**Interfaces:**
- Consumes: nothing new.
- Produces: no signature changes — purely tuning constants on existing classes.

- [ ] **Step 1: Lower `Waveform.GAIN` and increase the fall-off rate**

In `caspr/ui/overlay.py`, change:

```python
class Waveform(QWidget):
    """Scrolling mic-level bars; a traveling shimmer in processing mode."""

    BARS = 24
    GAIN = 2.2  # RMS levels are small; scale into the visible range
```

to:

```python
class Waveform(QWidget):
    """Scrolling mic-level bars; a traveling shimmer in processing mode."""

    BARS = 24
    GAIN = 1.3  # meter_level() now applies its own compression; less extra gain needed
```

And in `_tick`, change:

```python
            for i, target in enumerate(self._levels):
                shown = self._display[i]
                # rise instantly, fall smoothly
                self._display[i] = target if target > shown else shown + (target - shown) * 0.35
```

to:

```python
            for i, target in enumerate(self._levels):
                shown = self._display[i]
                # rise instantly, fall smoothly (but snappier than before)
                self._display[i] = target if target > shown else shown + (target - shown) * 0.55
```

- [ ] **Step 2: Shrink the oval's content margins**

In `Pill.__init__`, change:

```python
        layout = QHBoxLayout(self)
        layout.setContentsMargins(22 + _SHADOW, 10 + _SHADOW, 22 + _SHADOW, 10 + _SHADOW)
        layout.setSpacing(10)
```

to:

```python
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20 + _SHADOW, 6 + _SHADOW, 20 + _SHADOW, 6 + _SHADOW)
        layout.setSpacing(10)
```

- [ ] **Step 3: Sanity-check the module still imports and paints**

No automated test exists for this file (no `QApplication` fixture anywhere in this suite — established pattern, not a gap to fill here). Run:

Run: `uv run python -c "from PySide6.QtWidgets import QApplication; app = QApplication([]); from caspr.ui.overlay import Waveform; w = Waveform(); print(w.GAIN)"`
Expected: prints `1.3`, no errors.

- [ ] **Step 4: Commit**

```bash
git add caspr/ui/overlay.py
git commit -m "feat(pill): more reactive waveform, more compact oval padding"
```

---

### Task 3: `ClickHoldGesture` — the mouse gesture state machine

**Files:**
- Modify: `caspr/hotkeys.py` (add the new class, after `GestureInterpreter`)
- Test: `tests/test_hotkeys.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `ClickHoldGesture(*, start: Callable[[], None], commit: Callable[[], None], hold_min_s: float = 0.25)` with `press(now: float) -> None` and `release(now: float) -> None` — consumed by Task 7's `Pill`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_hotkeys.py`:

```python
from caspr.hotkeys import ChordRecorder, ClickHoldGesture, PushToTalk, canonical_key, parse_chord


def _click_gesture():
    events = []
    g = ClickHoldGesture(
        start=lambda: events.append("start"), commit=lambda: events.append("commit")
    )
    return g, events


def test_hold_commits_on_release_after_hold_min():
    g, events = _click_gesture()
    g.press(0.0)
    assert events == ["start"]
    g.release(0.30)  # >= 0.25 default hold_min
    assert events == ["start", "commit"]


def test_quick_click_leaves_session_open():
    g, events = _click_gesture()
    g.press(0.0)
    g.release(0.10)  # < hold_min
    assert events == ["start"]  # no commit -- stays recording


def test_second_press_of_any_length_closes_open_session():
    g, events = _click_gesture()
    g.press(0.0)
    g.release(0.10)  # opens the session
    g.press(5.0)  # any later press closes it immediately, on press
    assert events == ["start", "commit"]
    g.release(5.05)  # the stop-click's own release is a no-op
    assert events == ["start", "commit"]


def test_hold_min_boundary_exactly_at_threshold_commits():
    g, events = _click_gesture()
    g.press(0.0)
    g.release(0.25)  # exactly hold_min: >= means "commit now"
    assert events == ["start", "commit"]


def test_extra_press_while_already_pressed_is_ignored():
    g, events = _click_gesture()
    g.press(0.0)
    g.press(0.05)  # stray extra down event while already pressed
    assert events == ["start"]
    g.release(0.30)
    assert events == ["start", "commit"]
```

(Keep the existing `from caspr.hotkeys import ChordRecorder, PushToTalk, canonical_key, parse_chord` import line at the top of the file — just add `ClickHoldGesture` to it, as shown above.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hotkeys.py -k ClickHoldGesture -v` (or just `-k click` / `-k hold_commits` etc. — there's no class wrapping these, so match by function name, e.g. `uv run pytest tests/test_hotkeys.py -v`)
Expected: FAIL with `ImportError: cannot import name 'ClickHoldGesture'`.

- [ ] **Step 3: Implement `ClickHoldGesture`**

Add to `caspr/hotkeys.py`, after the `GestureInterpreter` class (at the end of the file):

```python
class ClickHoldGesture:
    """Two-mode mouse gesture: hold-to-dictate, or click-to-start/click-to-stop.

    press() begins a session, or -- if a click-started session is already
    open -- ends it immediately (the stop happens on press, not release, so
    a stop-click's own duration never matters). release() decides what a
    session that began on THIS press should do: held >= hold_min_s means a
    deliberate hold, so it stops now. A quick release leaves the session
    open; recording continues until the next press.
    """

    def __init__(self, *, start, commit, hold_min_s: float = 0.25):
        self._start = start
        self._commit = commit
        self._hold_min = hold_min_s
        self._state = "idle"  # idle | pressed | open
        self._press_t = 0.0

    def press(self, now: float) -> None:
        if self._state == "open":
            self._commit()
            self._state = "idle"
            return
        if self._state == "idle":
            self._start()
            self._press_t = now
            self._state = "pressed"
        # state == "pressed": stray extra down event (e.g. auto-repeat) -- ignore

    def release(self, now: float) -> None:
        if self._state != "pressed":
            return  # no matching press-started session to close
        if now - self._press_t >= self._hold_min:
            self._commit()
            self._state = "idle"
        else:
            self._state = "open"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hotkeys.py -v`
Expected: all PASS (the 10 pre-existing tests plus the 5 new ones).

- [ ] **Step 5: Commit**

```bash
git add caspr/hotkeys.py tests/test_hotkeys.py
git commit -m "feat(pill): add ClickHoldGesture mouse gesture state machine"
```

---

### Task 4: `AppController.on_mouse_press`/`on_mouse_release`

**Files:**
- Modify: `caspr/app.py` (add two methods near `on_ptt_press`/`on_ptt_release`)
- Test: `tests/test_app_actions.py`

**Interfaces:**
- Consumes: nothing new (calls the existing private `_begin_recording()`/`_commit_recording()`).
- Produces: `AppController.on_mouse_press() -> None`, `AppController.on_mouse_release() -> None` — consumed by Task 7's `Pill` via a `ClickHoldGesture(start=controller.on_mouse_press, commit=controller.on_mouse_release)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app_actions.py`:

```python
def test_on_mouse_press_begins_recording(controller):
    controller._state = "idle"
    controller.on_mouse_press()
    assert controller.state == "recording"
    assert controller._recorder.started == 1


def test_on_mouse_release_commits_recording(controller, monkeypatch):
    subs = []
    monkeypatch.setattr(controller, "_pipeline", lambda audio: subs.append(audio))
    controller._state = "idle"
    controller.on_mouse_press()
    controller.on_mouse_release()
    assert len(subs) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_app_actions.py -k mouse -v`
Expected: FAIL with `AttributeError: 'AppController' object has no attribute 'on_mouse_press'`.

- [ ] **Step 3: Add the methods**

In `caspr/app.py`, right after the existing `on_ptt_press`/`on_ptt_release` methods (in the "hotkey callbacks" section):

```python
    def on_mouse_press(self) -> None:
        """Entry point for the pill's mouse gesture -- always the plain hold
        primitive, never routed through the keyboard's GestureInterpreter
        (mixing the two input devices into one gesture tracker risks a
        keyboard tap and a mouse click misfiring as a false double-tap)."""
        self._begin_recording()

    def on_mouse_release(self) -> None:
        self._commit_recording()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_app_actions.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add caspr/app.py tests/test_app_actions.py
git commit -m "feat(pill): add AppController.on_mouse_press/on_mouse_release"
```

---

### Task 5: `pill_always_visible` config field

**Files:**
- Modify: `caspr/config.py:28` (add the field)
- Modify: `caspr/ui/bridge_data.py` (settable-keys set, bool coercion, bootstrap payload)
- Test: `tests/test_bridge_data.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Config.pill_always_visible: bool` (default `True`); `bootstrap(controller)["pill_always_visible"]`; `apply_setting(controller, "pill_always_visible", value)` accepts a bool. Consumed by Task 6 (webui) and Task 7 (`Pill` reads `self._cfg.pill_always_visible`).

- [ ] **Step 1: Write the failing tests**

In `tests/test_bridge_data.py`, add `"pill_always_visible"` to the `BOOT_KEYS` set:

```python
BOOT_KEYS = {
    "user", "state", "paused", "hotkey", "hotkey_pretty", "model", "device",
    "engine", "language", "injection", "pill_linger_s", "sound_cues",
    "pill_always_visible",
    "input_device", "mics", "startup", "stats", "recent",
    "hotkey_toggle_dictation", "hotkey_toggle_dictation_pretty",
    "hotkey_cancel_dictation", "hotkey_cancel_dictation_pretty",
    "hotkey_mute_mic", "hotkey_mute_mic_pretty",
    "hotkey_open_history", "hotkey_open_history_pretty",
}
```

Then add two new test functions:

```python
def test_apply_setting_pill_always_visible_persists(tmp_path, monkeypatch):
    c, calls = _controller(tmp_path, monkeypatch)
    try:
        assert apply_setting(c, "pill_always_visible", False) == ""
        assert c.cfg.pill_always_visible is False
        assert load_config(tmp_path / "cfg.json").pill_always_visible is False
        assert calls == []
    finally:
        c.shutdown()


def test_bootstrap_exposes_pill_always_visible_default_true(tmp_path):
    controller = AppController(
        Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db"
    )
    try:
        boot = bootstrap(controller)
        assert boot["pill_always_visible"] is True
    finally:
        controller.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bridge_data.py -k pill_always_visible -v`
Expected: FAIL. `Config` has no `pill_always_visible` field yet, so
`test_apply_setting_pill_always_visible_persists` fails with
`AttributeError: 'Config' object has no attribute 'pill_always_visible'`
on the `assert c.cfg.pill_always_visible is False` line (the key isn't in
`_SETTING_KEYS` either, so `apply_setting` would have silently no-op'd
even before that). `test_bootstrap_exposes_pill_always_visible_default_true`
fails with `KeyError: 'pill_always_visible'` on `boot["pill_always_visible"]`.

- [ ] **Step 3: Add the config field**

In `caspr/config.py`, right after `sound_cues: bool = True  # soft ticks on record start/stop`:

```python
    pill_always_visible: bool = True  # idle mini-bar shown even when not recording
```

- [ ] **Step 4: Wire it into `bridge_data.py`**

In `caspr/ui/bridge_data.py`, add `"pill_always_visible"` to `_SETTING_KEYS` (right after `"sound_cues"`):

```python
_SETTING_KEYS = {
    "model",
    "device",
    "engine",
    "language",
    "injection",
    "pill_linger_s",
    "sound_cues",
    "pill_always_visible",
    "input_device",
    ...
```

Add `"pill_always_visible"` to the boolean-coercion branch in `apply_setting`:

```python
    elif key in ("sound_cues", "pill_always_visible", "cleanup_enabled", "handsfree_double_tap", "smart_correct"):
        value = bool(value)
```

Add it to the `bootstrap()` payload, right after `"sound_cues": cfg.sound_cues,`:

```python
        "sound_cues": cfg.sound_cues,
        "pill_always_visible": cfg.pill_always_visible,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_bridge_data.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q`
Expected: all PASS (no other test hardcodes the `Config` field list in a way this would break — `load_config`'s field-filtering is generic).

- [ ] **Step 7: Commit**

```bash
git add caspr/config.py caspr/ui/bridge_data.py tests/test_bridge_data.py
git commit -m "feat(pill): add pill_always_visible config field"
```

---

### Task 6: Settings toggle (webui)

**Files:**
- Modify: `webui/src/bridge.ts` (the `Bootstrap` interface)
- Modify: `webui/src/state.tsx` (the `MOCK_BOOT` object)
- Modify: `webui/src/pages/Settings.tsx` (new toggle row)

**Interfaces:**
- Consumes: `pill_always_visible` from Task 5's `bootstrap()` payload (same field name, so no mapping needed).
- Produces: no new exports — this is a leaf UI addition.

- [ ] **Step 1: Add the field to the `Bootstrap` interface**

In `webui/src/bridge.ts`, add `pill_always_visible: boolean` right after `sound_cues: boolean`:

```typescript
  pill_linger_s: number
  sound_cues: boolean
  pill_always_visible: boolean
  cleanup_enabled: boolean
```

- [ ] **Step 2: Add the field to `MOCK_BOOT`**

In `webui/src/state.tsx`, add `pill_always_visible: true,` right after `sound_cues: true,`:

```typescript
  pill_linger_s: 6,
  sound_cues: true,
  pill_always_visible: true,
  cleanup_enabled: true,
```

- [ ] **Step 3: Add the Settings toggle row**

In `webui/src/pages/Settings.tsx`, inside the `FEEDBACK` section, right after the existing `"Sound cues"` row:

```tsx
        <Row label="Sound cues">
          <Toggle checked={boot.sound_cues} onChange={(on) => set('sound_cues', on)} />
        </Row>
        <Row label="Always show the recording bar" note="a small bar stays on screen even when idle">
          <Toggle
            checked={boot.pill_always_visible}
            onChange={(on) => set('pill_always_visible', on)}
          />
        </Row>
      </Section>
```

(Only the new `<Row>` block is added — the surrounding `<Row label="Sound cues">` and the closing `</Section>` already exist; match against them to place it correctly.)

- [ ] **Step 4: Typecheck/build**

Run: `cd webui && npm run build`
Expected: succeeds.

- [ ] **Step 5: Commit**

```bash
git add webui/src/bridge.ts webui/src/state.tsx webui/src/pages/Settings.tsx
git commit -m "feat(pill): add Settings toggle for the always-visible mini-bar"
```

---

### Task 7: Idle mini-bar mode, resize/reposition, hover tooltip, mouse wiring

**Files:**
- Modify: `caspr/ui/overlay.py` (the bulk of the feature: idle-mode rendering, mode-aware resize, tooltip, mouse events)
- Modify: `caspr/__main__.py:163` (pass `controller` into `Pill`)

**Interfaces:**
- Consumes: `ClickHoldGesture` (Task 3), `AppController.on_mouse_press`/`on_mouse_release` (Task 4), `cfg.pill_always_visible` (Task 5), `pretty_chord` (existing, `caspr/hotkeys.py`), `MUTED`/`FG` (existing, `caspr/ui/style.py`).
- Produces: `Pill(cfg, controller)` — signature changes from `Pill(cfg)` to take `controller` too; every other public method (`on_state`, `set_level`, `show_transcript`, `expand_requested` signal) keeps its exact existing signature, so `__main__.py`'s other wiring lines (`controller.state_changed.connect(pill.on_state)` etc.) don't change.

- [ ] **Step 1: Add imports and module constants**

In `caspr/ui/overlay.py`, change the import lines:

```python
from .icons import glyph_icon
from .style import ACCENT, CORAL, FG, FLAG, HAIRLINE, SURFACE, flagged_html
```

to:

```python
from ..hotkeys import ClickHoldGesture, pretty_chord
from .icons import glyph_icon
from .style import ACCENT, CORAL, FG, FLAG, HAIRLINE, MUTED, SURFACE, flagged_html
```

And add these constants near the existing `FADES_ENABLED`/`_SHADOW`/`_BOTTOM_GAP`/`_MIC_GLYPH` block:

```python
_IDLE_W = 56  # idle mini-bar width, not hovering
_IDLE_HOVER_W = 64  # idle mini-bar width, hovering
_IDLE_H = 5  # idle mini-bar height (fixed, doesn't change on hover)
_IDLE_GAP = 8  # gap from screen bottom edge for the idle bar (vs _BOTTOM_GAP for the oval)
_QWIDGETSIZE_MAX = 16777215  # Qt's internal max widget dimension, for un-fixing a size
```

- [ ] **Step 2: Update `Pill.__init__`**

Change the signature and add the click-gesture wiring, mode tracking, and initial idle display. Replace:

```python
class Pill(QWidget):
    expand_requested = Signal(str)

    def __init__(self, cfg):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._cfg = cfg  # read pill_linger_s live so Settings changes apply instantly
        self._text = ""
        self._hiding = False
```

with:

```python
class Pill(QWidget):
    expand_requested = Signal(str)

    def __init__(self, cfg, controller):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._cfg = cfg  # read pill_linger_s/pill_always_visible live, Settings changes apply instantly
        self._text = ""
        self._hiding = False
        self._mode = "idle"  # idle | live | label
        self._hovering = False
        self._click_gesture = ClickHoldGesture(
            start=controller.on_mouse_press, commit=controller.on_mouse_release
        )
```

Then, at the very end of `__init__` (after the existing `self._fade.finished.connect(self._after_fade)` line), add:

```python
        if cfg.pill_always_visible:
            self._show_idle()
```

- [ ] **Step 3: Update `on_state` to return to idle instead of just hiding**

Replace:

```python
    def on_state(self, state: str, detail: str) -> None:
        if state == "recording":
            self._text = ""
            self._wave.reset()
            self._wave.set_mode("recording")
            self._show_live()
        elif state == "processing":
            self._wave.set_mode("processing")
        elif state == "error":
            self._show_label(f"<span style='color:{FLAG}'>⚠</span> {html.escape(detail)}")
            self._hide_timer.start(max(self._linger_ms, 2500))
```

with:

```python
    def on_state(self, state: str, detail: str) -> None:
        if state == "recording":
            self._text = ""
            self._wave.reset()
            self._wave.set_mode("recording")
            self._show_live()
        elif state == "processing":
            self._wave.set_mode("processing")
        elif state == "error":
            self._show_label(f"<span style='color:{FLAG}'>⚠</span> {html.escape(detail)}")
            self._hide_timer.start(max(self._linger_ms, 2500))
        elif state == "idle" and self._mode != "idle":
            # pipeline ended without a transcript (e.g. "didn't catch that") --
            # nothing else returns the pill to idle in that case, so do it here.
            if self._cfg.pill_always_visible:
                self._show_idle()
            else:
                self._fade_out()
```

- [ ] **Step 4: Update `_show_live`/`_show_label`, add `_show_idle` and `_unlock_size`**

Replace:

```python
    def _show_live(self) -> None:
        """Fixed-size glyph + waveform; geometry set once, no per-tick jumps."""
        self._hide_timer.stop()
        self._label.hide()
        self._wave.show()
        self._reposition()
        self._fade_in()

    def _show_label(self, html_text: str) -> None:
        self._hide_timer.stop()
        self._wave.hide()
        self._label.setText(html_text)
        self._label.show()
        self._reposition()
        self._fade_in()

    def _reposition(self) -> None:
        self._label.setMaximumWidth(560)
        self._label.setWordWrap(True)
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.bottom() - self.height() - _BOTTOM_GAP,
        )
```

with:

```python
    def _show_live(self) -> None:
        """Fixed-size glyph + waveform; geometry set once, no per-tick jumps."""
        self._mode = "live"
        self._hide_timer.stop()
        self._glyph.show()
        self._label.hide()
        self._wave.show()
        self._reposition()
        self._fade_in()

    def _show_label(self, html_text: str) -> None:
        self._mode = "label"
        self._hide_timer.stop()
        self._glyph.show()
        self._wave.hide()
        self._label.setText(html_text)
        self._label.show()
        self._reposition()
        self._fade_in()

    def _show_idle(self) -> None:
        self._mode = "idle"
        self._hide_timer.stop()
        self._glyph.hide()
        self._wave.hide()
        self._label.hide()
        self.setFixedSize(_IDLE_HOVER_W + 2 * _SHADOW, _IDLE_H + 2 * _SHADOW)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.bottom() - self.height() - _IDLE_GAP,
        )
        self.setToolTip(f"Click or hold to talk — {pretty_chord(self._cfg.hotkey)} works anywhere")
        self._fade_in()

    def _unlock_size(self) -> None:
        """Release the idle mode's setFixedSize() constraint so adjustSize()
        can grow the widget again for live/label mode."""
        self.setMinimumSize(0, 0)
        self.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)

    def _reposition(self) -> None:
        self._unlock_size()
        self._label.setMaximumWidth(560)
        self._label.setWordWrap(True)
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.bottom() - self.height() - _BOTTOM_GAP,
        )
```

- [ ] **Step 5: Update `_after_fade` to return to idle instead of hiding**

Replace:

```python
    def _after_fade(self) -> None:
        if self._hiding:
            self._hiding = False
            self.hide()
            self.setWindowOpacity(1.0)
```

with:

```python
    def _after_fade(self) -> None:
        if self._hiding:
            self._hiding = False
            self.setWindowOpacity(1.0)
            if self._cfg.pill_always_visible:
                self._show_idle()
            else:
                self.hide()
```

- [ ] **Step 6: Branch `paintEvent` on mode, add `_paint_idle`**

Replace:

```python
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        body = QRectF(self.rect()).adjusted(_SHADOW, _SHADOW, -_SHADOW, -_SHADOW)
        # painted penumbra — QGraphicsDropShadowEffect is unreliable on
        # translucent top-level windows, so fake it with layered rects
        for inset, alpha, dy in ((6.0, 10, 3.0), (7.5, 16, 2.0), (9.0, 24, 1.0)):
            shadow = QRectF(self.rect()).adjusted(inset, inset + dy, -inset, -inset + dy)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(shadow, shadow.height() / 2, shadow.height() / 2)
        fill = QColor(SURFACE)
        fill.setAlpha(244)
        painter.setBrush(fill)
        painter.setPen(QColor(HAIRLINE))
        painter.drawRoundedRect(body, body.height() / 2, body.height() / 2)

    def mousePressEvent(self, _event) -> None:
        if self._text:
            self.hide()
            self.expand_requested.emit(self._text)
```

with:

```python
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._mode == "idle":
            self._paint_idle(painter)
        else:
            self._paint_oval(painter)

    def _paint_idle(self, painter: QPainter) -> None:
        w = _IDLE_HOVER_W if self._hovering else _IDLE_W
        color = QColor(FG if self._hovering else MUTED)
        color.setAlphaF(0.85 if self._hovering else 0.55)
        painter.setBrush(color)
        x = (self.width() - w) / 2
        y = (self.height() - _IDLE_H) / 2
        painter.drawRoundedRect(QRectF(x, y, w, _IDLE_H), _IDLE_H / 2, _IDLE_H / 2)

    def _paint_oval(self, painter: QPainter) -> None:
        body = QRectF(self.rect()).adjusted(_SHADOW, _SHADOW, -_SHADOW, -_SHADOW)
        # painted penumbra — QGraphicsDropShadowEffect is unreliable on
        # translucent top-level windows, so fake it with layered rects
        for inset, alpha, dy in ((6.0, 10, 3.0), (7.5, 16, 2.0), (9.0, 24, 1.0)):
            shadow = QRectF(self.rect()).adjusted(inset, inset + dy, -inset, -inset + dy)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(shadow, shadow.height() / 2, shadow.height() / 2)
        fill = QColor(SURFACE)
        fill.setAlpha(244)
        painter.setBrush(fill)
        painter.setPen(QColor(HAIRLINE))
        painter.drawRoundedRect(body, body.height() / 2, body.height() / 2)

    def enterEvent(self, event) -> None:
        if self._mode == "idle":
            self._hovering = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._mode == "idle":
            self._hovering = False
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, _event) -> None:
        if self._mode == "label":
            self.hide()
            self.expand_requested.emit(self._text)
        else:
            self._click_gesture.press(time.monotonic())

    def mouseReleaseEvent(self, _event) -> None:
        if self._mode != "label":
            self._click_gesture.release(time.monotonic())
```

- [ ] **Step 7: Wire `controller` into the `Pill` construction call**

In `caspr/__main__.py`, change:

```python
        pill = Pill(cfg)
```

to:

```python
        pill = Pill(cfg, controller)
```

- [ ] **Step 8: Sanity-check the module imports and constructs**

No automated Qt widget test exists for this file. Run:

Run: `uv run python -c "from PySide6.QtWidgets import QApplication; app = QApplication([]); from caspr.app import AppController; from caspr.config import Config; from caspr.ui.overlay import Pill; c = AppController(Config(), config_path='__pill_check_cfg.json', history_path='__pill_check_hist.db'); p = Pill(Config(), c); print(p._mode, p.width(), p.height()); c.shutdown()"`
Expected: prints `idle 84 25` (width = `_IDLE_HOVER_W + 2*_SHADOW` = 64+20=84; height = `_IDLE_H + 2*_SHADOW` = 5+20=25 — if the printed numbers differ, the constants weren't applied correctly), no errors. Delete the two throwaway files it creates (`__pill_check_cfg.json`, `__pill_check_hist.db`) afterward.

- [ ] **Step 9: Run the full test suite**

Run: `uv run pytest -q`
Expected: all PASS (this task has no new pytest coverage of its own — Qt widget code, per the established pattern — but must not have broken anything else).

- [ ] **Step 10: Commit**

```bash
git add caspr/ui/overlay.py caspr/__main__.py
git commit -m "feat(pill): add idle mini-bar mode, mouse gesture wiring, hover tooltip"
```

---

### Task 8: Final integration — build, full test run, manual QA

**Files:**
- Modify: `webui/dist/**` (rebuilt bundle, committed — the Qt shell loads it directly in production)

**Interfaces:**
- Consumes: everything from Tasks 1-7.
- Produces: nothing further downstream.

- [ ] **Step 1: Rebuild the webui bundle**

Run: `cd webui && npm run build`
Expected: succeeds.

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -q`
Expected: all pass. Count should be 157 (pre-plan baseline) + 1 (`test_quiet_signal_boosted_above_old_linear_value`) + 5 (`ClickHoldGesture` tests) + 2 (`on_mouse_press`/`on_mouse_release`) + 2 (`pill_always_visible` bridge tests) = 167.

- [ ] **Step 3: Manual QA**

Launch the app (`uv run python -m caspr`, or however it's normally started) and check, against the design doc's requirements:

- A small mini-bar is visible at the bottom-center of the screen at all times when the app is running and idle — not just during recording.
- Hovering the mini-bar brightens it slightly and shows a tooltip with the current hotkey.
- Holding the hotkey (keyboard) still works exactly as before.
- Clicking the mini-bar starts recording, and it visibly expands into the oval.
- Clicking the oval again stops recording (commits).
- Pressing and holding the mini-bar, then releasing, dictates only while held (same feel as the keyboard hold).
- Speaking at a normal volume now visibly moves the waveform bars noticeably more than before.
- After a dictation finishes (transcript shown, then the linger period ends), the widget shrinks back to the idle mini-bar — it does not disappear.
- In Settings → Feedback, toggling "Always show the recording bar" off and restarting a dictation cycle makes the pill behave like before (hidden except during active states).
- A clip too short/silent to transcribe ("didn't catch that") also correctly returns the pill to the idle mini-bar, not stuck showing the recording oval.

- [ ] **Step 4: Commit the rebuilt dist**

```bash
git add webui/dist
git commit -m "build: rebuild webui dist for persistent pill widget"
```

- [ ] **Step 5: Push**

```bash
git push origin main
```
