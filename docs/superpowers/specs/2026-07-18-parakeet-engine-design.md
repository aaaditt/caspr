# Dual STT engine: Parakeet for English (approved 2026-07-18)

Benchmarks (HF Open ASR leaderboard) show nvidia/parakeet-tdt-0.6b-v2 beats
whisper-large-v3-turbo on English accuracy (6.05 vs ~7.8 avg WER) while being
dramatically faster (onnx-asr RTFx ≈ 36 on desktop CPU, ≈ 57 on T4 CUDA vs the
1.76 s/clip Aadit measured for turbo on his GTX 1650). Aadit approved a
language-aware dual backend.

## Design

- New runtime dep: `onnx-asr[gpu,hub]` (onnxruntime; CUDA when available).
- `caspr/stt_parakeet.py` — `ParakeetTranscriber(device)` wrapping
  `onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2")`; same `.transcribe(audio,
  language, initial_prompt) -> Transcription` contract as `Transcriber`
  (prompt ignored — Parakeet has no dictionary biasing; replacements still
  apply downstream). `.device` reflects the active onnxruntime provider,
  `.name` = "parakeet" for status lines.
- `caspr/stt.py` — pure `pick_engine(engine, language)` + factory
  `create_transcriber(cfg)`. Routing: engine "parakeet"/"whisper" forced;
  "auto" → parakeet only when cfg.language == "en" (routing happens before
  audio exists, so auto-detect stays on whisper).
- `Config.engine: str = "auto"`.
- `AppController._load_model` uses the factory; status shows
  `{name} on {device}`.
- Settings → Transcription gains an Engine select (Auto / Parakeet — English,
  fastest / Whisper — all languages). `apply_setting`: "engine" reloads;
  "language" now also reloads (it steers auto-routing).
- Whisper path unchanged — Hindi/auto-detect keep working exactly as today.

## Out of scope

- pingala-v1-universal (better Hindi): the HF repo is **gated** — Aadit must
  request access at huggingface.co/shunyalabs/pingala-v1-universal and accept
  their license before it can even be downloaded. Revisit if/when granted.
- Streaming partial results (moonshine) — separate future feature.

## Verification

pick_engine unit tests; engine/language reload routing tests; live bench
script comparing turbo vs parakeet on a fixture WAV with real timings on this
machine; `uv run caspr` end-to-end with Language=English → status shows
"parakeet on …".
