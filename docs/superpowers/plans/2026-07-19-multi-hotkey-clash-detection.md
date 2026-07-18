# Multiple Keybindable Actions + Clash Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Aadit bind 4 new dictation actions (toggle dictation, cancel dictation, mute mic, open history) to custom hotkeys in Settings, alongside the existing push-to-talk hotkey, with live clash detection when a chord is already used by another action.

**Architecture:** Config grows 4 new optional chord fields (default unbound). Push-to-talk keeps its existing hold/release `PushToTalk` listener; the 4 new actions register as simple fire-on-press hotkeys via a new `SimpleHotkeys` registry wrapping `keyboard.add_hotkey`. The existing native `HotkeyCaptureDialog` becomes parameterized by action and checks the chord it just recorded against the other 4 actions' bound chords, blocking accept and showing an inline warning on a match instead of closing. The webui gains a "SHORTCUTS" settings section and a way for Python to tell the SPA to navigate to the History page (needed for the open-history action), which requires lifting page-routing state out of `App.tsx` into the shared `CasprProvider` context.

**Tech Stack:** Python 3.14, PySide6/Qt (native capture dialog), `keyboard` library (Windows low-level global hook), React + TypeScript (webui), QWebChannel (Python↔JS bridge), pytest.

## Global Constraints

- Push-to-talk (`Config.hotkey`) stays required and always bound — no "Clear" option, unaffected by this feature beyond the shared re-arm/suspend plumbing.
- The 4 new hotkey fields default to `""` (unbound); empty string is a valid, always-accepted value for them specifically (unlike `hotkey`, which still rejects empty/unparseable chords).
- Clash comparison must normalize left/right modifier sides (e.g. `"right ctrl"` and `"ctrl"` are the same physical key) — a naive string compare is wrong and must not be used.
- No OS-reserved-shortcut blocklist — out of scope per the approved spec.
- Old `config.json` files must keep loading unchanged (already true: `load_config` filters unknown keys; new fields just default).

---

## File Structure

| File | Responsibility |
|---|---|
| `caspr/config.py` | 4 new `Config` fields |
| `caspr/hotkeys.py` | `chords_equal`/`find_clash` (pure clash logic) + `SimpleHotkeys` (fire-on-press registry) |
| `caspr/app.py` | `AppController.cancel_dictation()` + `on_toggle_dictation()` |
| `caspr/ui/overlay.py` | `Pill.on_state` gains a cancelled-recording branch |
| `caspr/ui/bridge_data.py` | `apply_setting`/`bootstrap` cover the 4 new fields |
| `caspr/ui/hotkey_capture.py` | `HotkeyCaptureDialog` parameterized by action, live clash warning |
| `caspr/ui/bridge.py` | `capture_hotkey(action)`, `navigate_requested` signal, zero-arg `hotkey_changed` |
| `caspr/ui/shell.py` | relays `navigate_requested`, adds `open_history()` |
| `caspr/__main__.py` | arms/disarms all 5 hotkeys together, wires the 4 new callbacks |
| `webui/src/bridge.ts` | types for the 4 new bootstrap fields, `capture_hotkey(action, cb)`, `navigate_requested` |
| `webui/src/state.tsx` | owns `page` state, subscribes to `navigate_requested` |
| `webui/src/App.tsx` | split into `App` (provider) + `AppShell` (consumer) so it can read `page` from context |
| `webui/src/pages/Settings.tsx` | new SHORTCUTS section; existing push-to-talk row reuses the generalized capture flow |

Test files: `tests/test_config.py`, `tests/test_hotkeys.py`, `tests/test_bridge_data.py` (extended); `tests/test_app_actions.py` (new). No JS test runner exists in this repo (confirmed: no `test` script, no vitest/jest config) — front-end tasks are manually verified via `CASPR_UI_DEV=1 uv run caspr`, matching how the rest of the Qt/React glue in this codebase is already verified. This mirrors the codebase's existing split: pure logic (`hotkeys.py`, `bridge_data.py`, `app.py` state machine) is unit-tested; Qt widgets and `__main__.py` wiring are not.

---

### Task 1: Config — four new hotkey fields

**Files:**
- Modify: `caspr/config.py:14` (right after the existing `hotkey` field)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.hotkey_toggle_dictation: str`, `Config.hotkey_cancel_dictation: str`, `Config.hotkey_mute_mic: str`, `Config.hotkey_open_history: str` — all default `""`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:

```python
def test_new_hotkey_actions_default_unbound():
    cfg = Config()
    assert cfg.hotkey_toggle_dictation == ""
    assert cfg.hotkey_cancel_dictation == ""
    assert cfg.hotkey_mute_mic == ""
    assert cfg.hotkey_open_history == ""


def test_new_hotkeys_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(hotkey_toggle_dictation="f9", hotkey_mute_mic="ctrl+alt+m")
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.hotkey_toggle_dictation == "f9"
    assert loaded.hotkey_mute_mic == "ctrl+alt+m"
    assert loaded.hotkey_cancel_dictation == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'hotkey_toggle_dictation'`

- [ ] **Step 3: Add the fields**

In `caspr/config.py`, right after the `hotkey` field (line 14):

```python
    hotkey: str = "ctrl+windows"
    # Optional single-press actions; "" means unbound. Format identical to
    # `hotkey` (chord parts joined by "+"), but empty is valid here.
    hotkey_toggle_dictation: str = ""
    hotkey_cancel_dictation: str = ""
    hotkey_mute_mic: str = ""
    hotkey_open_history: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add caspr/config.py tests/test_config.py
git commit -m "config: add 4 optional hotkey fields for new bindable actions"
```

---

### Task 2: hotkeys.py — clash comparison helpers

**Files:**
- Modify: `caspr/hotkeys.py` (add after `canonical_key`, before `class ChordRecorder`)
- Test: `tests/test_hotkeys.py`

**Interfaces:**
- Consumes: `parse_chord(chord: str) -> list[str]`, `canonical_key(name: str) -> str` (both already exist in this file).
- Produces: `chords_equal(a: str, b: str) -> bool`, `find_clash(chord: str, other_bindings: dict[str, str]) -> str | None`. Used by Task 6 (capture dialog).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hotkeys.py` (extend the existing top import line to include the two new names):

```python
from caspr.hotkeys import (
    ChordRecorder,
    PushToTalk,
    canonical_key,
    chords_equal,
    find_clash,
    parse_chord,
)


def test_chords_equal_ignores_order_and_side():
    assert chords_equal("ctrl+windows", "windows+ctrl")
    assert chords_equal("right ctrl", "ctrl")
    assert chords_equal("Left Ctrl", "right ctrl")
    assert not chords_equal("ctrl+windows", "ctrl+alt")


def test_chords_equal_empty_never_matches():
    assert not chords_equal("", "ctrl")
    assert not chords_equal("ctrl", "")
    assert not chords_equal("", "")


def test_find_clash_returns_owning_label():
    bindings = {
        "Push-to-talk": "ctrl+windows",
        "Mute microphone": "ctrl+alt+m",
        "Cancel dictation": "",
    }
    assert find_clash("windows+ctrl", bindings) == "Push-to-talk"
    assert find_clash("f9", bindings) is None


def test_find_clash_normalizes_sided_modifiers():
    assert find_clash("right ctrl", {"Push-to-talk": "ctrl"}) == "Push-to-talk"


def test_find_clash_ignores_unbound_entries():
    assert find_clash("f9", {"Cancel dictation": ""}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hotkeys.py -v`
Expected: FAIL — `ImportError: cannot import name 'chords_equal'`

- [ ] **Step 3: Implement the helpers**

In `caspr/hotkeys.py`, after the `canonical_key` function (after line 50) and before `class ChordRecorder:`:

```python
def _canonical_chord(chord: str) -> frozenset[str]:
    """Order/side-independent form of a chord, for clash comparison."""
    return frozenset(canonical_key(part) for part in parse_chord(chord))


def chords_equal(a: str, b: str) -> bool:
    """True if two chord strings press the same physical keys, ignoring part
    order and left/right modifier side. Empty strings (unbound) never equal
    anything, including each other."""
    if not a or not b:
        return False
    return _canonical_chord(a) == _canonical_chord(b)


def find_clash(chord: str, other_bindings: dict[str, str]) -> str | None:
    """Return the label of the first entry in `other_bindings` whose chord
    equals `chord` (per chords_equal), or None if there's no clash. Unbound
    ("") entries are ignored."""
    for label, bound_chord in other_bindings.items():
        if bound_chord and chords_equal(chord, bound_chord):
            return label
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hotkeys.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add caspr/hotkeys.py tests/test_hotkeys.py
git commit -m "hotkeys: add chords_equal/find_clash for side-independent clash detection"
```

---

### Task 3: AppController — cancel_dictation + on_toggle_dictation, Pill fade fix

**Files:**
- Modify: `caspr/app.py:147-154` (insert after `on_ptt_release`, before the `-- pipeline --` section)
- Modify: `caspr/ui/overlay.py:141-151` (`Pill.on_state`)
- Test: `tests/test_app_actions.py` (new file)

**Interfaces:**
- Consumes: `AppController._state`, `AppController._recorder` (`.start()`/`.stop() -> np.ndarray`), `AppController._lock`, `AppController.state_changed` signal, `AppController.on_ptt_press()`/`on_ptt_release()` (all pre-existing).
- Produces: `AppController.cancel_dictation() -> None`, `AppController.on_toggle_dictation() -> None`. Consumed by Task 7 (`__main__.py` wiring).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app_actions.py`:

```python
"""cancel_dictation and on_toggle_dictation: the two new hotkey actions that
operate directly on AppController's recording state machine."""

import numpy as np

from caspr.app import AppController
from caspr.config import Config


class FakeRecorder:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True
        return np.zeros(0, dtype=np.float32)


def _controller(tmp_path):
    c = AppController(Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db")
    c._recorder = FakeRecorder()
    return c


def test_cancel_dictation_discards_recording(tmp_path):
    c = _controller(tmp_path)
    try:
        c._state = "recording"
        events = []
        c.state_changed.connect(lambda s, d: events.append((s, d)))
        c.cancel_dictation()
        assert c._state == "idle"
        assert c._recorder.stopped is True
        assert events == [("idle", "cancelled")]
    finally:
        c.shutdown()


def test_cancel_dictation_noop_when_not_recording(tmp_path):
    c = _controller(tmp_path)
    try:
        c._state = "idle"
        events = []
        c.state_changed.connect(lambda s, d: events.append((s, d)))
        c.cancel_dictation()
        assert events == []
        assert c._recorder.stopped is False
    finally:
        c.shutdown()


def test_toggle_dictation_starts_when_idle(tmp_path):
    c = _controller(tmp_path)
    try:
        c._state = "idle"
        c.on_toggle_dictation()
        assert c._state == "recording"
        assert c._recorder.started is True
    finally:
        c.shutdown()


def test_toggle_dictation_stops_when_recording(tmp_path):
    c = _controller(tmp_path)
    try:
        c._state = "recording"
        c.on_toggle_dictation()
        assert c._recorder.stopped is True
    finally:
        c.shutdown()


def test_toggle_dictation_ignored_while_paused(tmp_path):
    c = _controller(tmp_path)
    try:
        c._state = "idle"
        c.paused = True
        c.on_toggle_dictation()
        assert c._state == "idle"
        assert c._recorder.started is False
    finally:
        c.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_app_actions.py -v`
Expected: FAIL — `AttributeError: 'AppController' object has no attribute 'cancel_dictation'`

- [ ] **Step 3: Implement the controller methods**

In `caspr/app.py`, after `on_ptt_release` (ends at line 154) and before the `# -- pipeline (worker thread) --` comment:

```python
    def cancel_dictation(self) -> None:
        """Abort an in-progress recording: nothing is transcribed or injected."""
        with self._lock:
            if self._state != "recording":
                return
            self._state = "idle"
        self._recorder.stop()
        self.state_changed.emit("idle", "cancelled")

    def on_toggle_dictation(self) -> None:
        """Tap-to-start/tap-to-stop, as an alternative to holding push-to-talk."""
        if self._state == "idle" and not self.paused:
            self.on_ptt_press()
        elif self._state == "recording":
            self.on_ptt_release()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_app_actions.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Fix the pill so a cancelled recording doesn't hang open**

In `caspr/ui/overlay.py`, `Pill.on_state` (lines 141-151) currently has no branch for `state == "idle"`. `cancel_dictation` (Step 3) goes straight from `recording` to `idle` with detail `"cancelled"`, skipping the `processing`/`dictation_done` path that normally triggers `show_transcript` → fade-out. Without this, the live waveform pill stays on screen forever after a cancel. Add a branch:

```python
    def on_state(self, state: str, detail: str) -> None:
        if state == "recording":
            self._text = ""
            self._wave.reset()
            self._wave.set_mode("recording")
            self._show_live()
        elif state == "processing":
            self._wave.set_mode("processing")
        elif state == "idle" and detail == "cancelled":
            self._fade_out()
        elif state == "error":
            self._show_label(f"<span style='color:{FLAG}'>⚠</span> {html.escape(detail)}")
            self._hide_timer.start(max(self._linger_ms, 2500))
```

This is a Qt widget with no existing unit-test harness in this repo (confirmed: nothing in `tests/` instantiates a `QWidget`) — verify it manually in Task 7's end-to-end check instead of writing a test here.

- [ ] **Step 6: Commit**

```bash
git add caspr/app.py caspr/ui/overlay.py tests/test_app_actions.py
git commit -m "app: add cancel_dictation and on_toggle_dictation; fix pill hang on cancel"
```

---

### Task 4: hotkeys.py — SimpleHotkeys registry

**Files:**
- Modify: `caspr/hotkeys.py` (add after `class PushToTalk`, at end of file)
- Test: `tests/test_hotkeys.py`

**Interfaces:**
- Consumes: `keyboard.add_hotkey(chord: str, callback, suppress: bool) -> object`, `keyboard.remove_hotkey(handle) -> None` (from the `keyboard` package, already imported as `import keyboard` at the top of this file).
- Produces: `SimpleHotkeys` class with `.arm(name: str, chord: str, callback: Callable[[], None]) -> None`, `.disarm(name: str) -> None`, `.disarm_all() -> None`. Consumed by Task 7 (`__main__.py`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hotkeys.py`:

```python
import caspr.hotkeys as hotkeys_module
from caspr.hotkeys import SimpleHotkeys


def _fake_keyboard(monkeypatch):
    added = []
    removed = []

    def fake_add_hotkey(chord, callback, suppress=False):
        handle = object()
        added.append((chord, callback, handle))
        return handle

    def fake_remove_hotkey(handle):
        removed.append(handle)

    monkeypatch.setattr(hotkeys_module.keyboard, "add_hotkey", fake_add_hotkey)
    monkeypatch.setattr(hotkeys_module.keyboard, "remove_hotkey", fake_remove_hotkey)
    return added, removed


def test_simple_hotkeys_arm_registers_with_keyboard_lib(monkeypatch):
    added, _removed = _fake_keyboard(monkeypatch)
    hk = SimpleHotkeys()
    cb = lambda: None
    hk.arm("mute_mic", "ctrl+alt+m", cb)
    assert len(added) == 1
    assert added[0][0] == "ctrl+alt+m"
    assert added[0][1] is cb


def test_simple_hotkeys_arm_empty_chord_registers_nothing(monkeypatch):
    added, _removed = _fake_keyboard(monkeypatch)
    hk = SimpleHotkeys()
    hk.arm("mute_mic", "", lambda: None)
    assert added == []


def test_simple_hotkeys_rearm_removes_old_handle_first(monkeypatch):
    added, removed = _fake_keyboard(monkeypatch)
    hk = SimpleHotkeys()
    hk.arm("mute_mic", "ctrl+alt+m", lambda: None)
    first_handle = added[0][2]
    hk.arm("mute_mic", "f9", lambda: None)
    assert removed == [first_handle]
    assert len(added) == 2


def test_simple_hotkeys_disarm_all(monkeypatch):
    added, removed = _fake_keyboard(monkeypatch)
    hk = SimpleHotkeys()
    hk.arm("mute_mic", "ctrl+alt+m", lambda: None)
    hk.arm("cancel_dictation", "f9", lambda: None)
    hk.disarm_all()
    assert len(removed) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hotkeys.py -v`
Expected: FAIL — `ImportError: cannot import name 'SimpleHotkeys'`

- [ ] **Step 3: Implement the registry**

At the end of `caspr/hotkeys.py`, after `class PushToTalk`:

```python
class SimpleHotkeys:
    """Registers named single-press hotkeys: each fires once per completed
    press via keyboard.add_hotkey, unlike PushToTalk's hold/release pair.
    Used for every bindable action except push-to-talk itself."""

    def __init__(self):
        self._handles: dict[str, object] = {}

    def arm(self, name: str, chord: str, callback: Callable[[], None]) -> None:
        self.disarm(name)
        if chord:
            self._handles[name] = keyboard.add_hotkey(chord, callback, suppress=False)

    def disarm(self, name: str) -> None:
        handle = self._handles.pop(name, None)
        if handle is not None:
            keyboard.remove_hotkey(handle)

    def disarm_all(self) -> None:
        for name in list(self._handles):
            self.disarm(name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hotkeys.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add caspr/hotkeys.py tests/test_hotkeys.py
git commit -m "hotkeys: add SimpleHotkeys registry for fire-on-press actions"
```

---

### Task 5: bridge_data.py — settings + bootstrap for the 4 new fields

**Files:**
- Modify: `caspr/ui/bridge_data.py`
- Test: `tests/test_bridge_data.py`

**Interfaces:**
- Consumes: `Config.hotkey_toggle_dictation`/`hotkey_cancel_dictation`/`hotkey_mute_mic`/`hotkey_open_history` (Task 1), `parse_chord`, `pretty_chord` (pre-existing in `caspr/hotkeys.py`).
- Produces: `apply_setting` accepts the 4 new keys (empty string always valid, non-empty must parse); `bootstrap()` includes `hotkey_<action>` and `hotkey_<action>_pretty` for all 4. Consumed by Task 7 (`bridge.py`) and Task 8 (`bridge.ts` types).

- [ ] **Step 1: Write the failing tests**

In `tests/test_bridge_data.py`, replace `BOOT_KEYS` (lines 16-20) with:

```python
BOOT_KEYS = {
    "user", "state", "paused", "hotkey", "hotkey_pretty", "model", "device",
    "engine", "language", "injection", "pill_linger_s", "sound_cues",
    "input_device", "mics", "startup", "stats", "recent",
    "hotkey_toggle_dictation", "hotkey_toggle_dictation_pretty",
    "hotkey_cancel_dictation", "hotkey_cancel_dictation_pretty",
    "hotkey_mute_mic", "hotkey_mute_mic_pretty",
    "hotkey_open_history", "hotkey_open_history_pretty",
}
```

Then append two new tests at the end of the file:

```python
def test_apply_setting_optional_hotkeys_accept_empty_and_valid(tmp_path, monkeypatch):
    c, calls = _controller(tmp_path, monkeypatch)
    try:
        assert apply_setting(c, "hotkey_mute_mic", "ctrl+alt+m") == "hotkey"
        assert c.cfg.hotkey_mute_mic == "ctrl+alt+m"
        assert apply_setting(c, "hotkey_mute_mic", "") == "hotkey"
        assert c.cfg.hotkey_mute_mic == ""
        assert apply_setting(c, "hotkey_cancel_dictation", "++") == ""
        assert c.cfg.hotkey_cancel_dictation == ""  # rejected, untouched
        assert calls == []
    finally:
        c.shutdown()


def test_bootstrap_includes_optional_hotkeys_unbound_by_default(tmp_path):
    controller = AppController(
        Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db"
    )
    try:
        boot = bootstrap(controller)
        assert boot["hotkey_mute_mic"] == ""
        assert boot["hotkey_mute_mic_pretty"] == ""
    finally:
        controller.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bridge_data.py -v`
Expected: FAIL — `test_bootstrap_shape` and the two new tests fail (missing keys / `apply_setting` returns `""` for the unknown new keys)

- [ ] **Step 3: Extend `_SETTING_KEYS` and `apply_setting`**

In `caspr/ui/bridge_data.py`, replace `_SETTING_KEYS` (lines 15-25) with:

```python
_SETTING_KEYS = {
    "model",
    "device",
    "engine",
    "language",
    "injection",
    "pill_linger_s",
    "sound_cues",
    "input_device",
    "hotkey",
    "hotkey_toggle_dictation",
    "hotkey_cancel_dictation",
    "hotkey_mute_mic",
    "hotkey_open_history",
}

_OPTIONAL_HOTKEY_KEYS = {
    "hotkey_toggle_dictation",
    "hotkey_cancel_dictation",
    "hotkey_mute_mic",
    "hotkey_open_history",
}
```

In `apply_setting`, extend the elif chain (currently ends with the `hotkey` branch at lines 45-47):

```python
    elif key == "hotkey":
        if not isinstance(value, str) or not parse_chord(value):
            return ""
    elif key in _OPTIONAL_HOTKEY_KEYS:
        if not isinstance(value, str):
            return ""
        if value and not parse_chord(value):
            return ""
```

And change the follow-up return (currently `if key == "hotkey": return "hotkey"`):

```python
    if key == "hotkey" or key in _OPTIONAL_HOTKEY_KEYS:
        return "hotkey"
```

- [ ] **Step 4: Extend `bootstrap()`**

In `caspr/ui/bridge_data.py`, in the `bootstrap()` dict literal, right after the existing `"hotkey_pretty": pretty_chord(cfg.hotkey),` line:

```python
        "hotkey_toggle_dictation": cfg.hotkey_toggle_dictation,
        "hotkey_toggle_dictation_pretty": pretty_chord(cfg.hotkey_toggle_dictation),
        "hotkey_cancel_dictation": cfg.hotkey_cancel_dictation,
        "hotkey_cancel_dictation_pretty": pretty_chord(cfg.hotkey_cancel_dictation),
        "hotkey_mute_mic": cfg.hotkey_mute_mic,
        "hotkey_mute_mic_pretty": pretty_chord(cfg.hotkey_mute_mic),
        "hotkey_open_history": cfg.hotkey_open_history,
        "hotkey_open_history_pretty": pretty_chord(cfg.hotkey_open_history),
```

(`pretty_chord("")` already returns `""` — `parse_chord("")` is `[]`, and `" + ".join([])` is `""` — no special-casing needed.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_bridge_data.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 6: Run the full test suite to check nothing else regressed**

Run: `uv run pytest -v`
Expected: PASS (all tests, including ones from Tasks 1-4)

- [ ] **Step 7: Commit**

```bash
git add caspr/ui/bridge_data.py tests/test_bridge_data.py
git commit -m "bridge_data: apply_setting/bootstrap cover the 4 new hotkey fields"
```

---

### Task 6: hotkey_capture.py — parameterized dialog with live clash warning

**Files:**
- Modify: `caspr/ui/hotkey_capture.py`

**Interfaces:**
- Consumes: `find_clash(chord: str, other_bindings: dict[str, str]) -> str | None` (Task 2), `FLAG` color constant (`caspr/ui/style.py`, already `#ff5c49`, already used for flagged-word warnings elsewhere).
- Produces: `HotkeyCaptureDialog(action_label: str, other_bindings: dict[str, str] | None = None, parent=None)`. Consumed by Task 7 (`bridge.py`).

No automated test — this is a `QDialog` with a real global keyboard hook; the existing test suite has no Qt widget test harness (`test_hotkeys.py` tests `ChordRecorder`/`PushToTalk`'s internal logic directly, never through a Qt event loop). Verified manually as part of Task 7's end-to-end check.

- [ ] **Step 1: Update imports and constructor**

In `caspr/ui/hotkey_capture.py`, change the imports (lines 12-17):

```python
import keyboard
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from ..hotkeys import ChordRecorder, find_clash
from .style import APP_QSS, FLAG
```

Replace the constructor (lines 27-48):

```python
    def __init__(self, action_label: str, other_bindings: dict[str, str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Set {action_label}")
        self.setStyleSheet(APP_QSS)
        self.setModal(True)
        self.chord: str | None = None
        self._other_bindings = other_bindings or {}
        self._recorder = ChordRecorder()
        self._hook = None

        prompt = QLabel("Press the shortcut you want, then release.")
        hint = QLabel("Esc cancels.")
        hint.setObjectName("caption")
        self._held = QLabel("waiting…")
        self._held.setObjectName("h1")
        self._held.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._warning = QLabel("")
        self._warning.setStyleSheet(f"color: {FLAG};")
        self._warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._warning.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(prompt)
        layout.addWidget(self._held)
        layout.addWidget(self._warning)
        layout.addWidget(hint)
        self.setFixedWidth(360)

        self._event.connect(self._on_event)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(_TIMEOUT_MS)
        self._timeout.timeout.connect(self.reject)
```

- [ ] **Step 2: Block accept on a clash**

Replace `_on_event` (lines 78-89):

```python
    def _on_event(self, kind: str, name: str) -> None:  # GUI thread
        if name == "esc":
            self.reject()
            return
        self._timeout.start()  # any activity resets the 10 s deadline
        self._recorder.feed(kind, name)
        if self._recorder.chord is not None:
            clash = find_clash(self._recorder.chord, self._other_bindings)
            if clash:
                self._warning.setText(f"Already used by {clash} — try a different combo.")
                self._recorder = ChordRecorder()
                self._held.setText("waiting…")
                return
            self.chord = self._recorder.chord
            self.accept()
            return
        held = self._recorder.held
        self._held.setText(" + ".join(part.title() for part in held) if held else "waiting…")
```

- [ ] **Step 3: Update the module docstring's stale caller reference**

The module docstring (lines 1-8) says "The caller MUST stop the armed PushToTalk before opening this dialog" — still true, but now applies to all 5 armed hotkeys, not just PushToTalk. Update line 6-7:

```python
"""Modal dialog that records a global hotkey chord via the keyboard library.

Qt's QKeySequenceEdit cannot see the Windows key, so we hook the same keyboard
library used to arm every hotkey. The caller MUST suspend all armed hotkeys
before opening this dialog (Bridge.capture_hotkey handles this via
capture_active), or holding a chord that's already bound to another action
would also fire that action mid-capture.
"""
```

- [ ] **Step 4: Verify the file is syntactically valid**

Run: `uv run python -c "import caspr.ui.hotkey_capture"`
Expected: no output, exit code 0 (this only checks import/syntax — full behavior is verified manually in Task 7)

- [ ] **Step 5: Commit**

```bash
git add caspr/ui/hotkey_capture.py
git commit -m "hotkey_capture: parameterize dialog by action, block accept on clash"
```

---

### Task 7: bridge.py + shell.py + __main__.py — wire all 5 hotkeys together

**Files:**
- Modify: `caspr/ui/bridge.py`
- Modify: `caspr/ui/shell.py`
- Modify: `caspr/__main__.py`

**Interfaces:**
- Consumes: `SimpleHotkeys` (Task 4), `AppController.cancel_dictation`/`on_toggle_dictation`/`toggle_pause` (Task 3 + pre-existing), `HotkeyCaptureDialog(action_label, other_bindings)` (Task 6), `apply_setting` (Task 5).
- Produces: `Bridge.capture_hotkey(action: str) -> str | None` (was zero-arg), `Bridge.navigate_requested` signal, `Bridge.hotkey_changed` signal (now zero-arg, was `Signal(str)`), `Shell.open_history() -> None`. Consumed by Task 8 (`bridge.ts` types) and Task 10 (`Settings.tsx`).

No automated test for this task (Qt wiring + global OS hooks; `__main__.py` has no existing test coverage in this repo). Verified manually in Step 5.

- [ ] **Step 1: Update `bridge.py` signals and `set_setting`**

In `caspr/ui/bridge.py`, change the signal declarations (lines 34-35):

```python
    hotkey_changed = Signal()  # any hotkey changed — caller re-arms everything
    capture_active = Signal(bool)  # True while the capture dialog's hook is live
    navigate_requested = Signal(str)  # relayed by Shell so the SPA can switch pages
```

Update `set_setting` (lines 96-99):

```python
    @Slot(str, "QVariant")
    def set_setting(self, key: str, value) -> None:
        if apply_setting(self._controller, key, value) == "hotkey":
            self.hotkey_changed.emit()
```

- [ ] **Step 2: Generalize `capture_hotkey`**

Add as module-level constants above `class Bridge` (same placement pattern as the existing `_EDGES` dict at lines 16-25):

```python
_ACTION_LABELS = {
    "push_to_talk": "Push-to-talk",
    "toggle_dictation": "Toggle dictation",
    "cancel_dictation": "Cancel dictation",
    "mute_mic": "Mute microphone",
    "open_history": "Open history",
}
_ACTION_FIELDS = {
    "push_to_talk": "hotkey",
    "toggle_dictation": "hotkey_toggle_dictation",
    "cancel_dictation": "hotkey_cancel_dictation",
    "mute_mic": "hotkey_mute_mic",
    "open_history": "hotkey_open_history",
}
```

Replace `capture_hotkey` (lines 101-115):

```python
    @Slot(str, result="QVariant")
    def capture_hotkey(self, action: str):
        """Modal Qt capture (global hooks can't live in the web layer).
        All armed hotkeys are suspended around it via capture_active."""
        from .hotkey_capture import HotkeyCaptureDialog

        field = _ACTION_FIELDS.get(action)
        if field is None:
            return None
        cfg = self._controller.cfg
        other_bindings = {}
        for other_action, label in _ACTION_LABELS.items():
            other_field = _ACTION_FIELDS[other_action]
            if other_field != field:
                other_bindings[label] = getattr(cfg, other_field)

        self.capture_active.emit(True)
        try:
            dialog = HotkeyCaptureDialog(_ACTION_LABELS[action], other_bindings)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.chord:
                self.set_setting(field, dialog.chord)
                return dialog.chord
            return None
        finally:
            self.capture_active.emit(False)
```

- [ ] **Step 3: Update `shell.py`**

In `caspr/ui/shell.py`, change the signal declarations (lines 25-26):

```python
class Shell(QWidget):
    hotkey_changed = Signal()
    capture_active = Signal(bool)
    navigate_requested = Signal(str)
```

In `__init__`, after the existing relay connections (lines 46-47):

```python
        self._bridge.hotkey_changed.connect(self.hotkey_changed)
        self._bridge.capture_active.connect(self.capture_active)
        self._bridge.navigate_requested.connect(self.navigate_requested)
```

Add a new method (anywhere in the class body, e.g. after `surface`):

```python
    def open_history(self) -> None:
        self.surface()
        self._bridge.navigate_requested.emit("history")
```

- [ ] **Step 4: Rewrite the `__main__.py` hotkey wiring block**

In `caspr/__main__.py`, add to the imports:

```python
from .hotkeys import PushToTalk, SimpleHotkeys
```

Replace the existing wiring block (from `ptt_holder: dict[str, PushToTalk] = {}` through `window.surface()`, lines 163-179):

```python
        ptt_holder: dict[str, PushToTalk] = {}
        simple = SimpleHotkeys()
        simple_actions = {
            "toggle_dictation": (lambda: cfg.hotkey_toggle_dictation, controller.on_toggle_dictation),
            "cancel_dictation": (lambda: cfg.hotkey_cancel_dictation, controller.cancel_dictation),
            "mute_mic": (lambda: cfg.hotkey_mute_mic, controller.toggle_pause),
            "open_history": (lambda: cfg.hotkey_open_history, window.open_history),
        }

        def arm_ptt() -> None:
            if "ptt" in ptt_holder:
                ptt_holder["ptt"].stop()
            ptt_holder["ptt"] = PushToTalk(
                cfg.hotkey, controller.on_ptt_press, controller.on_ptt_release
            )
            ptt_holder["ptt"].start()

        def arm_all() -> None:
            arm_ptt()
            for name, (get_chord, callback) in simple_actions.items():
                simple.arm(name, get_chord(), callback)

        def disarm_all() -> None:
            if "ptt" in ptt_holder:
                ptt_holder["ptt"].stop()
            simple.disarm_all()

        def on_capture_active(active: bool) -> None:
            if active:
                disarm_all()
            else:
                arm_all()

        arm_all()
        window.hotkey_changed.connect(arm_all)
        # Suspend every armed hotkey while the capture dialog owns the raw hook
        window.capture_active.connect(on_capture_active)
        window.surface()
```

- [ ] **Step 5: Manual end-to-end verification**

Run: `uv run pytest -v` — confirm everything from Tasks 1-6 still passes (this task adds no new automated tests, but a typo here would break imports for the whole app).

Then run: `CASPR_UI_DEV=1 uv run caspr` (with `npm run dev` running in `webui/` for hot reload, per the existing dev workflow) and manually verify:
1. Existing push-to-talk hotkey still works (hold, speak, release → text injected).
2. Open Settings, bind "Mute microphone" to `ctrl+alt+m` via the capture dialog — confirm it saves.
3. Try to bind "Cancel dictation" to the same `ctrl+alt+m` — confirm the dialog shows "Already used by Mute microphone" and stays open instead of closing.
4. Bind "Cancel dictation" to a free combo (e.g. `f8`) — confirm it saves.
5. Press-and-hold push-to-talk to start recording, then press `f8` — confirm the pill fades out and nothing is transcribed (check no new entry appears in History).
6. Bind "Toggle dictation" to `f9` — press once (recording starts), press again (stops, transcribes as usual).
7. Bind "Open history" to `f10`, minimize/hide the window, press `f10` — confirm the window raises. (Full page-navigation only lands in Task 9; for now confirm the window raises without erroring even though the page won't switch yet.)
8. While one capture dialog is open, confirm none of the other 4 hotkeys fire (e.g. hold push-to-talk's chord while the "Cancel dictation" capture dialog is open — no recording should start).

- [ ] **Step 6: Commit**

```bash
git add caspr/ui/bridge.py caspr/ui/shell.py caspr/__main__.py
git commit -m "wire all 5 hotkeys: capture_hotkey(action), suspend/rearm together, open_history"
```

---

### Task 8: webui/src/bridge.ts — types for the new fields and signals

**Files:**
- Modify: `webui/src/bridge.ts`

**Interfaces:**
- Consumes: the `bootstrap()` shape from Task 5, the `capture_hotkey`/`navigate_requested` shapes from Task 7.
- Produces: updated `Bootstrap` and `CasprApi` TypeScript interfaces. Consumed by Task 9 (`state.tsx`) and Task 10 (`Settings.tsx`).

- [ ] **Step 1: Extend the `Bootstrap` interface**

In `webui/src/bridge.ts`, in the `Bootstrap` interface (lines 11-29), after `hotkey_pretty: string`:

```ts
export interface Bootstrap {
  user: string
  state: string
  paused: boolean
  hotkey: string
  hotkey_pretty: string
  hotkey_toggle_dictation: string
  hotkey_toggle_dictation_pretty: string
  hotkey_cancel_dictation: string
  hotkey_cancel_dictation_pretty: string
  hotkey_mute_mic: string
  hotkey_mute_mic_pretty: string
  hotkey_open_history: string
  hotkey_open_history_pretty: string
  model: string
  device: string
  engine: string
  language: string
  injection: string
  pill_linger_s: number
  sound_cues: boolean
  input_device: number | null
  mics: { index: number; name: string }[]
  startup: boolean
  stats: { today: number; words: number; avg_s: number }
  recent: Entry[]
}
```

- [ ] **Step 2: Update `CasprApi`**

In the `CasprApi` interface (lines 44-67), change `capture_hotkey` and add `navigate_requested`:

```ts
export interface CasprApi {
  win_minimize(): void
  win_close(): void
  win_drag(): void
  win_resize(edge: string): void
  get_bootstrap(cb: (boot: Bootstrap) => void): void
  get_history(query: string, cb: (entries: Entry[]) => void): void
  delete_entry(id: number): void
  copy_text(text: string): void
  correct(text: string): void
  get_dictionary(cb: (d: Dictionary) => void): void
  learn_term(term: string): void
  forget_term(term: string): void
  forget_rule(wrong: string): void
  set_setting(key: string, value: unknown): void
  capture_hotkey(action: string, cb: (chord: string | null) => void): void
  set_startup(enabled: boolean): void
  toggle_pause(): void
  state_changed: QSignal<(state: string, detail: string) => void>
  input_level: QSignal<(level: number) => void>
  dictation_done: QSignal<(text: string, spans: [number, number][]) => void>
  paused_changed: QSignal<(paused: boolean) => void>
  data_changed: QSignal<() => void>
  navigate_requested: QSignal<(page: string) => void>
}
```

- [ ] **Step 3: Verify it type-checks**

Run (from `webui/`): `npx tsc --noEmit`
Expected: errors in `state.tsx`/`Settings.tsx` about the old `capture_hotkey(cb)` call shape — expected at this point, since those files aren't updated until Tasks 9-10. Confirm there are no errors in `bridge.ts` itself.

- [ ] **Step 4: Commit**

```bash
git add webui/src/bridge.ts
git commit -m "bridge.ts: types for the 4 new hotkeys, capture_hotkey(action), navigate_requested"
```

---

### Task 9: webui/src/state.tsx + App.tsx — page state moves into context

**Files:**
- Modify: `webui/src/state.tsx`
- Modify: `webui/src/App.tsx`

**Interfaces:**
- Consumes: `navigate_requested` signal (Task 8), `Page` type (`webui/src/components/Sidebar.tsx`, pre-existing: `'home' | 'history' | 'dictionary' | 'settings'`).
- Produces: `Caspr` context gains `page: Page` and `navigate(p: Page): void`. Consumed by Task 10 implicitly (via `useCaspr()`, though Settings.tsx doesn't need `page` directly).

- [ ] **Step 1: Add `page` to the context**

In `webui/src/state.tsx`, add an import at the top:

```ts
import type { Page } from './components/Sidebar'
```

Extend the `Caspr` interface (lines 30-38):

```ts
export interface Caspr {
  boot: Bootstrap
  state: string
  detail: string
  paused: boolean
  levels: number[]
  api: CasprApi | null
  page: Page
  navigate(p: Page): void
  refresh(): void
}
```

In `CasprProvider`, add state (alongside the other `useState` calls, e.g. after `const [api, setApi] = useState<CasprApi | null>(null)`):

```ts
  const [page, setPage] = useState<Page>('home')
```

In the bridge-signal-wiring `useEffect`, after the existing `bridgeApi.data_changed.connect(() => refresh())` line:

```ts
      bridgeApi.navigate_requested.connect((p) => setPage(p as Page))
```

Update the returned context value:

```ts
  return (
    <Ctx.Provider value={{ boot, state, detail, paused, levels, api, page, navigate: setPage, refresh }}>
      {children}
    </Ctx.Provider>
  )
```

- [ ] **Step 2: Split `App.tsx` into a provider shell and a consumer**

`App` currently owns `page` via local `useState` and renders `<CasprProvider>` around the JSX that uses it — a component can't consume a context it renders itself, so the page-switching UI needs to move into a child of the provider. Replace all of `webui/src/App.tsx`:

```tsx
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { ResizeEdges } from './components/ResizeEdges'
import { Sidebar, type Page } from './components/Sidebar'
import { TitleBar } from './components/TitleBar'
import { Dictionary } from './pages/Dictionary'
import { History } from './pages/History'
import { Home } from './pages/Home'
import { Settings } from './pages/Settings'
import { CasprProvider, useCaspr } from './state'

const PAGES: Record<Page, React.ComponentType> = {
  home: Home,
  history: History,
  dictionary: Dictionary,
  settings: Settings,
}

function AppShell() {
  const { page, navigate } = useCaspr()
  const reduce = useReducedMotion()
  const Current = PAGES[page]

  return (
    <div className="relative flex h-full">
      <ResizeEdges />
      <Sidebar page={page} onNavigate={navigate} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TitleBar />
        <main className="flex-1 overflow-y-auto px-8 pb-8">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={page}
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="h-full"
            >
              <Current />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <CasprProvider>
      <AppShell />
    </CasprProvider>
  )
}
```

- [ ] **Step 3: Verify it type-checks**

Run (from `webui/`): `npx tsc --noEmit`
Expected: errors only in `Settings.tsx` (old `capture_hotkey(cb)` call) — fixed in Task 10. No errors in `state.tsx` or `App.tsx`.

- [ ] **Step 4: Manual verification**

With `CASPR_UI_DEV=1 uv run caspr` and `npm run dev` running: confirm the sidebar still navigates between Home/History/Dictionary/Settings exactly as before (this step is a pure refactor — no visible behavior change yet, since nothing emits `navigate_requested` from a real hotkey until Task 10's Settings UI lets you bind Open History and Task 7's wiring is exercised again).

- [ ] **Step 5: Commit**

```bash
git add webui/src/state.tsx webui/src/App.tsx
git commit -m "state: lift page routing into CasprProvider so Python can drive navigation"
```

---

### Task 10: webui/src/pages/Settings.tsx — SHORTCUTS section

**Files:**
- Modify: `webui/src/pages/Settings.tsx`

**Interfaces:**
- Consumes: `Bootstrap` type (Task 8), `capture_hotkey(action, cb)` (Task 8), `set_setting(key, value)` (pre-existing), `Row`/`Section` components (pre-existing, this file).

- [ ] **Step 1: Import `Bootstrap` and define the action list**

In `webui/src/pages/Settings.tsx`, add to the imports at the top:

```tsx
import type { Bootstrap } from '../bridge'
```

Add near the other constant lists (after `PRESETS`, before `export function Settings()`):

```tsx
const SHORTCUT_ACTIONS: {
  key: string
  label: string
  field: keyof Bootstrap
  prettyField: keyof Bootstrap
  clearable: boolean
}[] = [
  { key: 'toggle_dictation', label: 'Toggle dictation', field: 'hotkey_toggle_dictation', prettyField: 'hotkey_toggle_dictation_pretty', clearable: true },
  { key: 'cancel_dictation', label: 'Cancel dictation', field: 'hotkey_cancel_dictation', prettyField: 'hotkey_cancel_dictation_pretty', clearable: true },
  { key: 'mute_mic', label: 'Mute microphone', field: 'hotkey_mute_mic', prettyField: 'hotkey_mute_mic_pretty', clearable: true },
  { key: 'open_history', label: 'Open history', field: 'hotkey_open_history', prettyField: 'hotkey_open_history_pretty', clearable: true },
]
```

- [ ] **Step 2: Replace the single-purpose `capturing`/`capture` state with a generalized version**

In `export function Settings()`, replace:

```tsx
  const [capturing, setCapturing] = useState(false)
```

with:

```tsx
  const [capturingAction, setCapturingAction] = useState<string | null>(null)
```

Replace the `capture` function:

```tsx
  const captureAction = (action: string) => {
    if (!api || capturingAction) return
    setCapturingAction(action)
    api.capture_hotkey(action, () => {
      setCapturingAction(null)
      refresh()
    })
  }
```

- [ ] **Step 3: Update the existing push-to-talk row to use the generalized flow**

In the DICTATION section, replace the Push-to-talk `Row`'s button (currently `onClick={capture}` / `disabled={capturing}` / `{capturing ? 'Press keys…' : 'Change…'}`):

```tsx
        <Row label="Push-to-talk">
          <span className="rounded-lg border border-hairline bg-raised px-3 py-1.5 text-[12.5px] font-medium tracking-wide text-amber">
            {boot.hotkey_pretty}
          </span>
          <button
            onClick={() => captureAction('push_to_talk')}
            disabled={capturingAction !== null}
            className="rounded-[10px] border border-hairline px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-raised disabled:opacity-50"
          >
            {capturingAction === 'push_to_talk' ? 'Press keys…' : 'Change…'}
          </button>
          <Select
            value={PRESETS.some((p) => p.value === boot.hotkey) ? boot.hotkey : ''}
            options={PRESETS.some((p) => p.value === boot.hotkey) ? PRESETS : [{ value: '', label: 'Custom' }, ...PRESETS]}
            onChange={(v) => v && set('hotkey', v)}
          />
        </Row>
```

- [ ] **Step 4: Add the SHORTCUTS section**

After the closing `</Section>` of DICTATION (before the TRANSCRIPTION section):

```tsx
      <Section title="SHORTCUTS">
        {SHORTCUT_ACTIONS.map((a) => (
          <Row key={a.key} label={a.label}>
            <span className="rounded-lg border border-hairline bg-raised px-3 py-1.5 text-[12.5px] font-medium tracking-wide text-amber">
              {(boot[a.prettyField] as string) || 'Not set'}
            </span>
            <button
              onClick={() => captureAction(a.key)}
              disabled={capturingAction !== null}
              className="rounded-[10px] border border-hairline px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-raised disabled:opacity-50"
            >
              {capturingAction === a.key ? 'Press keys…' : 'Change…'}
            </button>
            {a.clearable && boot[a.field] && (
              <button
                onClick={() => set(a.field, '')}
                className="rounded-[10px] border border-hairline px-2 py-1.5 text-[13px] text-muted transition-colors hover:bg-raised"
              >
                ×
              </button>
            )}
          </Row>
        ))}
      </Section>
```

- [ ] **Step 5: Verify it type-checks**

Run (from `webui/`): `npx tsc --noEmit`
Expected: no errors anywhere in `webui/src/`.

- [ ] **Step 6: Manual end-to-end verification**

With `CASPR_UI_DEV=1 uv run caspr` and `npm run dev` running, open Settings and confirm:
1. A new SHORTCUTS section renders with 4 rows, each showing "Not set".
2. Click "Change…" on Mute microphone, press `ctrl+alt+m` → row updates to "Ctrl + Alt + M".
3. Click "Change…" on Cancel dictation, press the same `ctrl+alt+m` → dialog shows "Already used by Mute microphone" inline and stays open; press `f8` instead → dialog closes, row updates to "F8".
4. Click the "×" next to Cancel dictation → row reverts to "Not set", and `set_setting('hotkey_cancel_dictation', '')` round-trips (refresh confirms it stays cleared after reload).
5. Bind Open history to `f10`, minimize the window, press `f10` → window raises AND the page switches to History (this is the first point where the full Task 7 + Task 9 wiring is exercised together).
6. Push-to-talk's row (preset dropdown + Change…) still works exactly as before.
7. While any one capture dialog is open, all "Change…" buttons for the other rows are disabled (`capturingAction !== null` guard).

- [ ] **Step 7: Commit**

```bash
git add webui/src/pages/Settings.tsx
git commit -m "Settings: add SHORTCUTS section for the 4 new hotkeys"
```

---

## Post-plan

Run the full backend suite once more (`uv run pytest -v`) and the full manual checklist from Tasks 7 and 10 together in one session before considering this feature done. Per project convention, commit and push to `origin/main` after the final task (Aadit wants every shipped feature on GitHub).
