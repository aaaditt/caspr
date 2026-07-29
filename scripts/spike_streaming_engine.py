"""Throwaway benchmark: does vosk (and optionally sherpa-onnx) give usable
live-typing latency/accuracy on this machine? Not part of the app.

Usage: .venv/Scripts/python.exe scripts/spike_streaming_engine.py <path_to_wav>
The wav must be 16kHz mono 16-bit PCM (use caspr.audio.load_wav_mono16k's
format — record one with the app, or `ffmpeg -ar 16000 -ac 1 -sample_fmt s16`).
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from caspr.audio import load_wav_mono16k, SAMPLE_RATE  # noqa: E402


def chunks(audio: np.ndarray, block_size: int = SAMPLE_RATE // 10):
    for i in range(0, len(audio), block_size):
        yield audio[i : i + block_size]


def bench_vosk(audio: np.ndarray, model_dir: str) -> None:
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    t_load = time.perf_counter()
    model = Model(model_dir)
    print(f"vosk model load: {time.perf_counter() - t_load:.2f}s")

    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(False)
    latencies = []
    last_partial = ""
    for block in chunks(audio):
        pcm = (np.clip(block, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        t0 = time.perf_counter()
        rec.AcceptWaveform(pcm)
        partial = json.loads(rec.PartialResult()).get("partial", "")
        latencies.append(time.perf_counter() - t0)
        if partial != last_partial:
            print(f"  partial: {partial!r}")
            last_partial = partial
    final = json.loads(rec.FinalResult()).get("text", "")
    print(f"vosk final: {final!r}")
    print(f"vosk per-chunk latency: mean={np.mean(latencies)*1000:.1f}ms max={np.max(latencies)*1000:.1f}ms")


if __name__ == "__main__":
    wav_path = sys.argv[1]
    audio = load_wav_mono16k(wav_path)
    model_dir = str(Path.home() / "AppData/Roaming/caspr-flow/models/vosk-model-small-en-us-0.15")
    bench_vosk(audio, model_dir)
