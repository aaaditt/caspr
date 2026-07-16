# caspr-flow — Correction & Learning UI

**Date:** 2026-07-16
**Status:** Approved (brainstormed with Aadit; pill→popup UX and dual learning chosen explicitly)

## Problem

Whisper misrecognizes personal vocabulary ("Aadit" → "Adit"/"audit"). Corrections
today mean hand-editing the pasted text and the same error recurs. The app should
flag suspect words, make adding them to the dictionary one right-click, and learn
explicit replacement rules for errors Whisper keeps making.

## UX (chosen: lingering pill → popup)

1. After each dictation is typed, the overlay pill lingers ~6s showing the final
   transcript with flagged words rendered red. The pill NEVER takes focus
   (Qt.WindowDoesNotAcceptFocus + WA_ShowWithoutActivating); ignoring it costs nothing.
2. Clicking the pill opens the correction popup (this one does take focus):
   - transcript in an editable text box; flagged words get red squiggles
     (QTextCharFormat.SpellCheckUnderline via a QSyntaxHighlighter)
   - right-click on a word → "Add '<word>' to dictionary" and
     "Always replace '<word>' → …" (input dialog)
   - "Copy corrected" button copies the edited text
3. Tray → History window: past dictations (SQLite) with the same
   underline/right-click treatment, plus a Dictionary tab listing terms and
   replacement rules with remove buttons.
4. While recording, the same pill shows the live mic level (delivers M2's overlay).

## Learning semantics

- **Add to dictionary** → term joins `config.dictionary` → flows into Whisper's
  `initial_prompt` (existing `build_initial_prompt`) → stops being flagged.
- **Replacement rule** → whole-word, case-insensitive match; replacement text
  inserted verbatim ("adit"/"Adit" → "Aadit"). Applied to every transcript
  post-STT, pre-injection.
- Free-form edits in the popup teach nothing by themselves — rules are only
  created by explicit right-click actions. No silent learning.

## Components

- `caspr/spellcheck.py` — `flag_unknown_words(text, personal_terms) -> [(start, end)]`.
  Word is flagged iff wordfreq zipf frequency < threshold (default 3.0, config
  `flag_zipf_threshold`) AND not in personal terms (case-insensitive) AND alphabetic.
  New dep: `wordfreq`.
- `caspr/replacements.py` — `apply_replacements(text, rules: dict[str, str]) -> str`.
- `caspr/history.py` — SQLite at %APPDATA%\caspr-flow\history.db:
  id, ts, raw_text, final_text, infer_s, total_s. `add()`, `recent(n)`, `delete(id)`.
- `caspr/ui/overlay.py` — pill widget (recording level / lingering transcript states).
- `caspr/ui/correct.py` — correction popup.
- `caspr/ui/history_view.py` — history + dictionary management window.
- Config additions: `replacements: dict[str, str]`, `flag_zipf_threshold: float`,
  `pill_linger_s: float` (0 disables the lingering pill entirely).

## Pipeline change (app.py)

transcribe → apply_replacements → inject → history.add → emit
`dictation_done(final_text, flagged_spans)` → overlay lingers.
Dictionary/replacement mutations save config immediately and take effect on the
next dictation (no restart).

## Testing

- TDD: spellcheck flagging (names "Aadit"/"Rahul" flagged; "meeting"/"testing" not;
  dictionary suppresses flags), replacement application (whole-word, case handling,
  no partial-word hits), history store round-trip.
- Live verification: dictate a name → pill lingers with red word → right-click add
  → next dictation recognizes/replaces correctly.

## Launcher & footprint (added on Aadit's review)

- `caspr` typed in any terminal launches the app **detached** — no console window,
  terminal immediately free. Mechanism: `[project.gui-scripts] caspr-app` entry
  (windowed, no console) + a `caspr.cmd` shim installed to
  `%LOCALAPPDATA%\Microsoft\WindowsApps` (already on PATH) that `start`s it.
  `uv run caspr` remains the dev mode with console logs.
- `caspr --startup on|off` creates/removes a shortcut in shell:startup so the app
  is always resident: invisible except the tray dot, activates on right-Ctrl.
- Single-instance lock already prevents duplicates; relaunching shows a message.
- Footprint honesty: ~300–500MB RAM (PySide6 + runtime) with model weights mostly
  in VRAM (~500MB of the 4GB card). Idle CPU ≈ 0%.

## Visual design (added on Aadit's review)

Wispr-like: minimal, rounded, calm. One QSS stylesheet shared by all windows.
- Pill: bottom-center above taskbar, frameless, translucent rounded capsule,
  dark charcoal bg, white text, subtle drop shadow; mic level as a soft pulsing
  dot; flagged words tinted red — no chrome, no buttons.
- Popup & history: frameless-ish light/dark cards, 12px radii, Segoe UI Variable,
  generous padding, one accent color (#4a90d9 family), no menu bars.

## Out of scope (this feature)

Groq cleanup (M2 proper, needs API key), per-app tone (M4), editing text already
typed into the target app (technically unreliable across foreign windows).
