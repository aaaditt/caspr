# Persistent Mini-Bar Pill Widget

*2026-07-30 — approved design.*

## Motivation

The floating recording indicator (`caspr/ui/overlay.py`'s `Pill`) currently
only appears during recording/processing/transcript-linger, hidden the rest
of the time. Aadit wants it visible at all times as a small, unobtrusive bar
(like an iOS home indicator) that expands into the current oval when
recording, mirroring Wispr Flow's always-on "Flow Bar." He also wants:
mouse click/hold on that bar to start and stop dictation (Wispr calls this
"Mouse Shortcuts"), a hover tooltip showing the hotkey, a more compact
recording oval, and a more visibly reactive waveform — the current one
barely moves for normal speaking volume.

Two decisions confirmed directly by Aadit:
- Mouse gesture stays simple: hold-to-dictate works, but click-to-toggle
  hands-free (double-click) is **not** built for the mouse — hands-free
  stays keyboard-only, to avoid a small bar misfiring on double-clicks.
- The always-on-screen bar gets a Settings toggle (`pill_always_visible`,
  default on), mirroring Wispr's "always-show Flow Bar" setting, so it can
  be turned off entirely (e.g. while screen-sharing).

Approved via the brainstorming visual companion: the mini-bar and expanded
oval shapes/sizes shown in mockups (`.superpowers/brainstorm/`, gitignored)
were confirmed as the right direction.

## Widget states

One `Pill` widget, always visible, resizing/repositioning itself between
three render modes, all anchored bottom-center of the screen:

1. **idle** (new) — the mini-bar: a 56×5px rounded line, `muted` color at
   ~55% opacity, sitting 8px above the screen's bottom edge. Hovering it
   brightens slightly (opacity → ~85%, width → 64px) and shows a tooltip:
   `"Click or hold to talk — {pretty_chord(hotkey)} works anywhere"`.
2. **live** (existing, resized) — today's recording/processing oval, same
   mic glyph + waveform bars, tighter padding for a shorter profile:
   content margins drop from `(22, 10, 22, 10)` to `(20, 6, 20, 6)` (plus
   the existing `_SHADOW` inset, unchanged).
3. **label** (existing, unchanged) — the transcript-linger oval. Behavior
   unchanged: shows for `pill_linger_s`, then transitions back to idle
   (previously: hides entirely).

Transitions between modes resize the window and reposition it so the
**bottom edge stays anchored** — the widget grows upward, not from center,
so it doesn't visually jump.

When `pill_always_visible` is off, behavior reverts to today: hidden except
during live/label modes (idle mode is simply never shown).

## Mouse gesture

A new small pure class in `caspr/hotkeys.py`, alongside the existing
`GestureInterpreter` (same pattern: no Qt dependency, timestamps injected
by the caller, fully unit-testable):

```
class ClickHoldGesture:
    """Two-mode mouse gesture: hold-to-dictate, or click-to-start/click-to-stop.

    press() always begins a session (or ends an already-open one, on the very
    click that reopens it — see below). release() decides what a session
    that began THIS press should do: if held >= hold_min_s, it was a
    deliberate hold, so it stops now. If it was a quick click, the session
    stays open — recording continues — until the next press.
    """

    def __init__(self, *, start, commit, hold_min_s: float = 0.25):
        self._start = start
        self._commit = commit
        self._hold_min = hold_min_s
        self._open = False       # a click-started session is running
        self._press_t = 0.0

    def press(self, now: float) -> None:
        if self._open:
            self._commit()
            self._open = False
            return
        self._start()
        self._press_t = now

    def release(self, now: float) -> None:
        if now - self._press_t >= self._hold_min:
            self._commit()
        else:
            self._open = True
```

`AppController` gets two new entry points mirroring the existing
`on_ptt_press`/`on_ptt_release` (which route through the keyboard's
`GestureInterpreter` when hands-free is on) but wired directly to the
plain hold primitives instead, with no gesture branching:

```python
def on_mouse_press(self) -> None:
    self._begin_recording()

def on_mouse_release(self) -> None:
    self._commit_recording()
```

`Pill` owns one `ClickHoldGesture` instance (`start=controller.on_mouse_press,
commit=controller.on_mouse_release`). Its existing `mousePressEvent` already
has a job in label mode — clicking a lingering transcript opens the
correction dialog (`if self._text: ... expand_requested.emit(...)`). That
takes priority; `ClickHoldGesture` gets the event in every other case
(idle **and** live mode), since "click again to stop" means the second
click must register while the widget is already showing the expanded oval,
not just in idle mode:

```python
def mousePressEvent(self, _event) -> None:
    if self._text:
        self.hide()
        self.expand_requested.emit(self._text)
    else:
        self._click_gesture.press(time.monotonic())

def mouseReleaseEvent(self, _event) -> None:
    if not self._text:
        self._click_gesture.release(time.monotonic())
```

Mouse input is deliberately **not** fed into the keyboard's
`GestureInterpreter` — sharing one gesture tracker between two independent
input devices risks a keyboard tap and a mouse click landing close enough
together to misfire as a false double-tap.

## Sensitivity & compactness

Root cause of "barely reacts to voice": `audio.meter_level()` scales mic
RMS linearly (`rms * sqrt(2)`, capped at 1.0), and normal speaking volume is
quiet relative to full-scale — so it produces small values most of the
time. Fix: apply power-law compression, which is the standard technique for
audio level meters (it visibly boosts quiet-to-moderate input while still
capping loud input at 1.0):

```python
def meter_level(block: np.ndarray) -> float:
    if block.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
    level = min(1.0, rms * np.sqrt(2.0))
    return level ** 0.5  # compress quiet input upward; tune exponent live
```

This function feeds both the Qt pill's waveform *and* the webui Home page's
live meter (`AppController.input_level` → both consumers) — one fix
improves both. Since the source signal is now more generous,
`caspr/ui/overlay.py`'s `Waveform.GAIN` (currently `2.2`, layered on top to
compensate for the old under-scaling) drops to `1.3`, so the two boosts
don't stack into constant clipping at 1.0. `Waveform._tick()`'s fall-off
smoothing factor (currently `0.35` — how far each frame moves toward a
falling target) increases to `0.55` for a snappier, twitchier feel matching
"flicker more." All three numbers (`0.5` exponent, `1.3` gain, `0.55`
falloff) are starting points meant to be verified live and adjusted if they
still don't feel right — perceptual tuning isn't fully solvable on paper,
but these are concrete, reasoned starting values, not placeholders.

## Config

One new field in `caspr/config.py`:

```python
pill_always_visible: bool = True  # idle mini-bar shown even when not recording
```

One new Settings row (`webui/src/pages/Settings.tsx`, under the existing
`FEEDBACK` section, alongside `Sound cues`): `"Always show the recording
bar"` — a `Toggle` bound to this field, following the exact pattern already
used for `sound_cues`.

## Scope — files touched

- `caspr/ui/overlay.py` — `Pill` gains idle-mode rendering, mode-aware
  resize/reposition (bottom-anchored), hover tooltip, `mousePressEvent`/
  `mouseReleaseEvent` wired to a `ClickHoldGesture`; `Waveform`'s `GAIN`
  and fall-off constant retuned; live-mode content margins tightened.
- `caspr/hotkeys.py` — new `ClickHoldGesture` class.
- `caspr/app.py` — new `on_mouse_press()`/`on_mouse_release()` methods on
  `AppController`.
- `caspr/audio.py` — `meter_level()` gains power-law compression.
- `caspr/config.py` — new `pill_always_visible` field.
- `caspr/ui/bridge_data.py` — add `pill_always_visible` alongside
  `sound_cues` in the settable-fields tuple (line ~22), the boolean-field
  coercion check (line ~66), and the boot-payload dict (line ~163).
- `webui/src/pages/Settings.tsx` — new toggle row.
- `caspr/__main__.py` — `Pill` is shown immediately at creation instead of
  staying hidden until the first state change (so idle mode is visible from
  app start), gated on `cfg.pill_always_visible`.

## Non-goals

- No change to the mic glyph icon in the recording/live oval — padding
  shrinks, the icon itself stays as-is (the visual mockup used a plain red
  dot as a quick illustration shorthand; that swap was never confirmed and
  isn't part of this design).
- No hands-free (double-click) support for the mouse gesture — explicitly
  ruled out by Aadit.
- No changes to `pill_linger_s`/transcript-label behavior beyond "return to
  idle mini-bar instead of hiding" — the linger duration, flagged-word
  styling, and click-to-expand-into-correction-dialog behavior are
  untouched.
- No changes to the keyboard hotkey path (`GestureInterpreter`,
  `HotkeyService`) — this design adds a second, independent input path,
  it doesn't touch the first.

## Verification

`ClickHoldGesture` is a pure class like `GestureInterpreter` — unit tested
the same way (inject timestamps, assert on `start`/`commit` call order,
covering: quick click leaves it open, a second click of any length closes
it, a deliberate hold commits on release, hold-min boundary behavior).
`meter_level()`'s new compression curve gets a unit test asserting the
curve shape (low input maps well above its old linear value; full-scale
input still caps at 1.0). Everything else (widget resize/reposition,
tooltip, mouse events, actual on-screen feel of the sensitivity/falloff
tuning) is manual verification — no automated test harness exists for Qt
widget painting/geometry in this repo (established pattern from the recent
rebrand), and perceptual "does it flicker enough" tuning is definitionally
a manual call.
