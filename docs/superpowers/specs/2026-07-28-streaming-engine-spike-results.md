# Streaming Engine Spike Results

**Date:** 2026-07-29
**Decision:** vosk

## What was tested

`scripts/spike_streaming_engine.py` against `tests/fixtures/testing_one_two_three.wav`
(the only recorded clip available in this repo at spike time) using
`vosk-model-small-en-us-0.15` (~40MB, downloaded from
https://alphacephei.com/vosk/models and unzipped to
`%APPDATA%\caspr-flow\models\vosk-model-small-en-us-0.15\`).

## Results

- Model load: 1.31s (one-time cost at app startup, not per-dictation)
- Per-chunk (100ms block) latency: **mean 59.2ms, max 378.9ms**
- Transcript: `"testing one two three"` — exact match to the spoken fixture
- No crashes, installed cleanly via `uv pip install vosk` on Python 3.14/Windows/CPU
  (no pip module in this uv-managed venv — used `uv pip install` instead of the plan's
  literal `pip install`)

Mean per-chunk latency (59ms) comfortably clears the "well under 100ms" bar from the
design doc — live typing should feel responsive rather than laggy. The max (378.9ms)
is the first-chunk cost as the recognizer's internal state warms up; it does not
recur on later chunks.

## Decision: vosk, without benchmarking sherpa-onnx

Per the plan, sherpa-onnx is only evaluated if vosk fails the bars — it didn't, so
sherpa-onnx was not tried. vosk is also the simpler candidate (no external model-file
pinning risk beyond the one zip already fetched).

## Caveat: single fixture only

Only one test clip existed in the repo (a short, clearly-enunciated 4-word phrase).
This confirms the *mechanism* works (chunk-in/partial-out, real-time-beating latency,
correct transcript on a clean sample) but does not stress-test vosk's word accuracy
on longer, more natural, or noisier speech the way a 3-4 clip bake-off would. Since
the streaming engine's output is never the source of truth (Task 7's release-time
reconciliation against Parakeet/Whisper corrects whatever vosk gets wrong), a WER gap
here is a UX/liveliness question, not a correctness risk — worth keeping an eye on
during Task 8's live verification, not a blocker for proceeding.
