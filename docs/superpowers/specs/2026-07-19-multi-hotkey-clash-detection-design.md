# Multiple keybindable actions + clash detection (approved 2026-07-19)

Today caspr has exactly one hotkey: push-to-talk (`Config.hotkey`), hold-based,
set via a native Qt capture dialog (`HotkeyCaptureDialog`) or a preset dropdown
in Settings. Aadit asked for more actions to be bindable, plus a warning when a
new binding collides with one already in use.

## New actions

Four new optional, unbound-by-default actions alongside the existing
required push-to-talk:

| Action | Behavior | Backend hook |
|---|---|---|
| `toggle_dictation` | tap once to start recording, tap again to stop+transcribe | reuses `AppController.on_ptt_press`/`on_ptt_release` |
| `cancel_dictation` | abort an in-progress recording, nothing transcribed/injected | new `AppController.cancel_dictation()` |
| `mute_mic` | pause/resume, same as the existing tray/UI toggle | existing `AppController.toggle_pause()` |
| `open_history` | raise the main window on the History page | new Bridge signal, no controller change |

## Data model

`caspr/config.py` gets four new fields, default `""` (unbound):

```python
hotkey: str = "ctrl+windows"        # push-to-talk — unchanged, always required
hotkey_toggle_dictation: str = ""
hotkey_cancel_dictation: str = ""
hotkey_mute_mic: str = ""
hotkey_open_history: str = ""
```

No migration needed — `load_config` already filters unknown JSON keys, so
existing config.json files keep loading; the new fields default to unbound.

## Backend wiring

- Push-to-talk is unchanged: still a `PushToTalk` hold/release listener.
- The 4 new actions are registered with `keyboard.add_hotkey(chord, callback,
  suppress=False)` — fire-once-on-press, no hold-tracking needed. Skipped
  entirely when the chord is `""`.
- `AppController.cancel_dictation()`: if state is `"recording"`, stop the
  recorder (discard the returned audio instead of running the pipeline) and
  set state back to `"idle"`. **`Pill.on_state` currently has no branch for
  this transition** — recording → idle with no `processing`/`dictation_done`
  step in between — so the pill would otherwise hang open indefinitely. Add a
  case that fades it out on a cancelled state.
- `open_history`: a new `Bridge`/`Shell` signal (mirroring how
  `hotkey_changed` already relays Python → JS) that `App.tsx` listens for to
  set `page = 'history'`, paired with `window.surface()` to raise+focus.
- `__main__.py`'s wiring grows a small registry (action → armed handle) so all
  5 hotkeys can be re-armed when their chord changes and, critically,
  **suspended together** while any capture dialog has its raw hook open —
  today `capture_active` only stops push-to-talk; it must stop all 5, or
  pressing another action's chord mid-capture would both fire that action
  *and* feed the recorder.

## Clash detection

Lives entirely in `HotkeyCaptureDialog`, which already exists for
push-to-talk and already builds chords live via `ChordRecorder`:

- `capture_hotkey` becomes `capture_hotkey(action: str)` on the Bridge. It
  looks up the human label + chord for the other 4 actions from `cfg`
  (skipping unbound ones) and passes them into the dialog.
- The dialog's title becomes `f"Set {action_label}"` instead of the hardcoded
  "Set push-to-talk".
- Today, the instant `ChordRecorder.chord` finalizes, the dialog calls
  `self.accept()`. That becomes conditional: if the finalized chord matches
  one of the other bound chords, don't accept — show an inline warning
  ("Already used by Push-to-talk") in place of the "waiting…" label, reset a
  fresh `ChordRecorder`, and keep the hook listening. The user just keeps
  pressing until they land on something free, or Esc to cancel as before.
- **Comparison normalizes left/right modifiers** the same way
  `ChordRecorder` already does internally (`canonical_key`: "right ctrl" and
  "ctrl" collapse to the same key) — otherwise a chord recorded live (which
  can never produce a sided name; the recorder always canonicalizes) could
  fail to match an existing binding set via the preset dropdown's raw string
  (e.g. push-to-talk = `"right ctrl"` from a preset), even though physically
  they're the same key press. This needs a small shared helper in
  `hotkeys.py` rather than a naive string compare.
- No OS-reserved-shortcut blocklist. Out of scope: genuinely OS-intercepted
  combos (Ctrl+Alt+Del) never reach the `keyboard` hook regardless, so there's
  nothing to warn about there.

## Settings UI

New `SHORTCUTS` section in `webui/src/pages/Settings.tsx`, below DICTATION,
listing all 5 actions. Each row: current chord as a pill (or "Not set" when
unbound), a "Change…" button that calls `capture_hotkey(action)` (same
capturing-state pattern as today's push-to-talk row), and — for the 4
optional actions only — a small "Clear" (×) button that calls
`set_setting(field, "")`. Push-to-talk keeps its existing row (chord pill +
Change… + preset dropdown) untouched; no clear button, since the app always
needs a way to start dictation.

`bridge_data.py`'s `_SETTING_KEYS` allowlist and `apply_setting` gain the 4
new field names; empty string is a valid value for those four (unlike
`hotkey`, which still rejects empty/unparseable chords).

## Out of scope

- Per-side modifier distinctions as first-class bindable chords (e.g. binding
  "left ctrl" and "right ctrl" to two different actions) — the capture
  recorder can't produce sided output today, and adding that is unrelated to
  this feature.
- OS-shortcut blocklist (see above).
- Changing push-to-talk's required/always-bound status.

## Verification

Unit tests: the new clash-comparison helper (including the sided-modifier
case), `cancel_dictation` state transitions, `apply_setting` accepting empty
string for the 4 optional fields and still rejecting it for `hotkey`. Manual:
`uv run caspr`, bind all 4 new actions to distinct chords, verify each fires;
try to bind `cancel_dictation` to push-to-talk's chord (and to `"right ctrl"`
if push-to-talk is set to `"ctrl"` or vice versa) and confirm the dialog
blocks it with the clash message; cancel an in-progress recording and confirm
the pill fades instead of hanging; open history via hotkey while the window
is hidden and confirm it raises on the History page.
