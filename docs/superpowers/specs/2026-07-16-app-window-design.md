# caspr-flow — Main App Window, Chord Hotkey, Dark Restyle

**Date:** 2026-07-16
**Status:** Approved (Ctrl+Win chord and window design chosen by Aadit)

## Problem

caspr currently lives only as a tray dot — launching it gives no visible app.
Wispr Flow pairs the background dictation with a real dashboard window. Aadit
wants that: `caspr` opens an app window (and arms dictation); the window hides
to tray on close; re-running `caspr` surfaces it. Also: replace right-Ctrl with
a Wispr-style chord. Fn cannot be hooked on Windows (firmware handles it), so
the chosen default is **Ctrl + Win** — Wispr's own Windows default; modifier-only
chords type nothing into the focused app.

## UX

1. `caspr` → main window opens + dictation armed. Closing the window hides it
   (tray + hotkey stay live). Tray gains "Open caspr" (replaces "History &
   dictionary"); tray icon click also opens the window.
2. Second `caspr` invocation surfaces the running instance's window and exits.
3. Window: dark Wispr-like shell — near-black bg (#131316), card surfaces
   (#1c1d22), teal accent (#22d3ee), rounded 12px cards, Segoe UI Variable.
   Left sidebar nav: Home, Dictionary, History, Settings.
   - **Home:** status card (live state dot, model/device, "Hold Ctrl + Win
     anywhere" hint) + stat cards (dictations today, total words, avg latency)
     + 5 most recent dictations.
   - **Dictionary:** existing terms/rules management page.
   - **History:** existing dictations list (double-click → correction popup).
   - **Settings:** hotkey preset dropdown (Ctrl+Win, right-Ctrl, Ctrl+Alt),
     model dropdown (base/small/large-v3-turbo with speed hints), language
     (auto/en/hi), injection method, pill linger seconds, launch-at-login
     checkbox (reuses --startup logic). Hotkey rebinds live; model/language
     show "restart to apply".

## Components

- `caspr/ui/main_window.py` — sidebar shell + Home/Settings pages; Dictionary
  and History pages extracted from `history_view.py` (which is deleted).
- `caspr/ui/style.py` — dark palette app-wide: BG #131316, SURFACE #1c1d22,
  ACCENT #22d3ee, FG #f4f4f5, muted #8b8b93. Pill unchanged (already dark).
- `caspr/hotkeys.py` — `PushToTalk` accepts chords: config string split on `+`
  (e.g. "ctrl+windows"), each part hooked press/release, on_press fires when all
  parts are down (once), on_release when any part lifts. `parse_chord(str) ->
  list[str]` is pure (TDD).
- `caspr/history.py` — `stats() -> Stats(today_count, total_words, avg_total_s)`
  (TDD; words = whitespace split of final_text).
- `caspr/__main__.py` — QLocalServer "caspr-flow": first instance listens
  (message "show" → surface window); second instance connects, sends "show",
  exits 0. Replaces the QLockFile print-and-die path. Config default hotkey
  becomes "ctrl+windows" (existing configs: user edits or Settings).
- Window close → hide() (no quit); Quit stays in tray menu only.

## Out of scope

Groq cleanup (M2), onboarding wizard, wake word, model hot-reload.

## Testing

- TDD: `parse_chord`, chord state logic (press/release ordering incl. repeat
  debounce), `History.stats`, settings persistence via existing config tests.
- Manual: window opens on `caspr`; second `caspr` surfaces it; close hides;
  Ctrl+Win dictates into Notepad with no Start menu popping; settings edits
  persist to config.json; stats match history.
