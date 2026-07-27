# Live Streaming Dictation — Design

**Date:** 2026-07-27
**Status:** Approved (design); implementation pending

## What & why

Aadit reported three problems in one session:

1. A cleanup-pipeline bug where the injected text included content from prior dictations
   ("copied everything I've ever said") — root-caused and fixed same session (see
   `caspr/cleanup.py`, no design doc needed: a one-file fix with a context-leak guard and
   preamble stripper, TDD'd, 157 tests green).
2. The Groq cloud cleanup call adding a slow round-trip after every dictation. **Resolved
   without code changes** — `cleanup_enabled` already has a working Settings toggle
   (`webui/src/pages/Settings.tsx:299` → `bridge_data.py` → `cfg.cleanup_enabled`); Aadit
   toggled it off himself rather than changing the code default.
3. The real ask: dictation should **type live, while he's still talking** — not record,
   wait, then paste — matching Wispr Flow's live-typing feel, using local models only (no
   cloud round-trip), prioritizing speed and accuracy.

This document covers **item 3 only** — the live-streaming architecture. Items 1 and 2 are
already shipped/resolved.

## The constraint that shapes everything

`onnx_asr` (wrapping Parakeet, `caspr/stt_parakeet.py`) is **batch-only**: its adapter layer
(`TextResultsAsrAdapter._recognize_batch`) takes a full waveform array and returns one
result. There is no incremental/stateful decode API — no way to feed it a growing buffer
and get cheap, O(1)-per-chunk partial hypotheses back. True live typing needs a genuinely
different decode shape than what the current pipeline provides.

## Architecture: two-track transcription

While the hotkey is held, a **streaming engine** consumes the same 100 ms audio blocks
`Recorder` already produces (`caspr/audio.py:75`, currently just appended to `self._blocks`)
and emits partial-word hypotheses as it goes. Each new hypothesis is diffed against what
caspr has typed into the focused window so far, and only the changed tail is corrected
(backspace + retype) — so words appear as they're recognized instead of after the whole
clip is transcribed.

On key release, the pipeline runs **exactly as it does today**: the full clip goes through
the existing accurate batch model (Parakeet/Whisper per `engine`/`language` routing),
`apply_replacements` runs, and **one final reconciliation diff** corrects whatever the fast
streaming engine got wrong against that accurate result. The text left on screen when a
dictation finishes is governed by the same trusted batch model as today — the streaming
engine's only job is to make the in-progress experience feel alive, not to be the source of
truth.

```
hold key ─┬─ Recorder callback (100ms blocks, unchanged)
          ├─ streaming engine: chunk → partial hypothesis → diff vs typed_text →
          │  backspace+retype the changed tail (repeats continuously while held)
          └─ release ─┬─ existing batch pipeline (Parakeet/Whisper, unchanged)
                       ├─ apply_replacements (unchanged)
                       └─ ONE reconciliation diff: typed_text → final corrected text
```

## Streaming engine: a spike, not a decision

No incremental-decode library is wired into this codebase today, and the last engine
addition (Parakeet, 2026-07-18) was itself chosen after a hands-on latency/WER bake-off on
this exact machine. The same discipline applies here: before writing any product code,
spike candidate libraries that expose a genuine chunk-in/partial-out API with internal
state (as opposed to onnx_asr's repeat-the-whole-buffer shape). Candidates to evaluate:
`vosk` (Kaldi-based, simple `AcceptWaveform`-per-chunk API, mature) and `sherpa-onnx`
(streaming zipformer models, generally lower latency/better accuracy than vosk on paper).
Neither has been benchmarked in this repo yet.

**Spike deliverable:** a throwaway script (not part of the app) that, for each candidate:
measures partial-hypothesis latency per chunk, rough English WER against a few recorded
test clips, and confirms the wheel installs cleanly under this repo's Python 3.14 / Windows
/ CPU-only-for-this-purpose environment (the GPU stays reserved for Whisper+games per
existing project convention). The winner becomes `caspr/stt_streaming.py`, following the
lazy-import, injectable-for-tests pattern already used by `stt_parakeet.py`/`stt_groq.py`.
If neither candidate is viable, fall back to periodically re-running Parakeet's batch
`recognize()` on the growing recording buffer (diffing each new full-clip result the same
way) rather than blocking the whole feature — accepting that this fallback's cost grows
with dictation length and will lag on longer hands-free sessions, unlike a true stateful
streaming decoder. This fallback should be a documented decision point in the plan, not a
silent one.

## Diff / reconciliation algorithm

Pure logic, no I/O, its own module (mirrors the `build_cleanup_messages` / `clean_text`
split already established in `cleanup.py`):

```python
def compute_correction(typed: str, target: str) -> tuple[int, str]:
    """Returns (backspace_count, text_to_type) to turn `typed` into `target`,
    diffing at word granularity so a word is never half-corrected mid-recognition."""
```

Applied identically for every live update and for the one release-time reconciliation
(release-time target = `apply_replacements(final_batch_text, cfg.replacements)`, so
replacement rules and batch-model correction land as a single combined diff rather than
two separate correction passes).

## Safety invariants

- **Never backspace more characters than caspr itself typed this session.** `typed_text`
  starts empty at record start; the backspace count computed by `compute_correction` is
  clamped to `len(typed_text)`. This is a hard invariant, not a tuning parameter — a diff
  bug must never be able to delete text the user typed before or around the dictation.
- **Streaming failure degrades to today's behavior, silently.** If the streaming engine
  fails to load or errors mid-session, live typing simply doesn't happen for that
  dictation (logged, not surfaced as an error) — recording continues normally, and release
  still runs the full existing batch pipeline and types the complete result once, exactly
  as caspr behaves today. Same never-lose-words philosophy as `cleanup.py`'s fallback: the
  fast path is best-effort, the existing batch path is the correctness backstop and does
  not change.

## Scope

- Both PTT-hold and hands-free double-tap get live typing — same `Recorder` audio path
  underneath both gesture modes, no separate implementation needed.
- `apply_replacements`/dictionary corrections apply **only at the final reconciliation**,
  not per live word. A word may render briefly with the wrong spelling and then correct
  itself once at release — intentional, keeps the live loop's diff target simple (raw
  streaming-engine output only, not a moving replacement-applied target).
- Cloud AI cleanup (Groq) is **out of scope** for this design — Aadit disabled it in
  Settings this session. Combining live streaming with cleanup re-enabled later is a
  future design problem (the reconciliation step would need to target cleaned text instead
  of raw batch text, which is a bigger diff — likely mostly-rewritten sentence rather than
  a short tail correction).
- `Recorder.MAX_SECONDS`, cancel-dictation, and pause behavior are unchanged; cancelling
  a dictation now also means backspacing away whatever was live-typed so far.

## Known limitation (accepted, not solved here)

If focus changes to a different window while the hotkey is held (e.g. alt-tab mid-
recording), live corrections land in whatever now has focus. This risk exists today too
(one-shot inject assumes focus hasn't moved), but is sharper here since there's continuous
activity instead of one paste. Detecting a focus change mid-recording and aborting live
typing is reasonable future hardening, not a blocker for this design.

## Testing (TDD)

- `compute_correction`: pure function, no mocking — word-boundary diffing, backspace-count
  clamping to session-typed length, identical-input no-op, full-replacement case.
- Streaming engine wrapper (`stt_streaming.py`, once the spike picks a library): same
  lazy-import/injectable pattern as `stt_parakeet.py`; unit tests inject a fake decoder.
- `AppController` wiring: integration tests following `test_app_cleanup.py`'s
  fake-recorder/fake-executor pattern — assert live diffs fire per streaming update, the
  release-time reconciliation diff runs against the batch result, and streaming-engine
  failure falls back to today's single full inject with no live corrections attempted.
- Existing 157 tests stay green throughout.

## Live/manual checks

- Dictate a short phrase, watch it type live word-by-word rather than appearing all at
  once after release.
- Dictate something the streaming engine mis-hears; confirm the release-time
  reconciliation silently corrects it in one clean diff, no leftover wrong words.
- Cancel a dictation mid-hold; confirm the live-typed text is fully backspaced away.
- Kill/disable the streaming engine (simulate load failure); confirm dictation still works
  exactly as it does today (one full inject at release, no live typing, no crash).

## Sequencing

1. Spike: benchmark `vosk` vs `sherpa-onnx` (latency, WER, installability) on this machine;
   pick one or fall back to rolling re-transcribe. This gates everything else.
2. `compute_correction` + its tests (pure logic, no dependency on the spike's outcome).
3. `stt_streaming.py` wrapper for the chosen engine + tests.
4. `AppController` wiring (live diff loop during recording, release-time reconciliation) +
   integration tests.
5. Live/manual verification, then commit + push per the standing rule.

## Out of scope

- Re-enabling Groq cleanup alongside live streaming (see Scope above).
- Fixing focus-change-mid-recording (see Known limitation above).
- Streaming/chunked cloud transcription — this design is local-only by design, matching
  Aadit's stated goal of removing the cloud round-trip.
