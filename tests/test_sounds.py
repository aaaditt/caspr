import wave

import numpy as np

from caspr.sounds import SAMPLE_RATE, ensure_cues, synth_cue


def test_synth_cue_shape_and_range():
    for kind in ("start", "stop"):
        samples = synth_cue(kind)
        assert samples.dtype == np.float32
        assert abs(len(samples) - SAMPLE_RATE * 0.08) <= 1
        peak = float(np.abs(samples).max())
        assert 0.2 <= peak <= 0.6  # audible but soft
        assert float(np.abs(samples).sum()) > 0


def test_start_and_stop_differ():
    assert not np.array_equal(synth_cue("start"), synth_cue("stop"))


def test_ensure_cues_writes_valid_wavs(tmp_path):
    paths = ensure_cues(tmp_path)
    assert set(paths) == {"start", "stop"}
    for path in paths.values():
        with wave.open(str(path), "rb") as f:
            assert f.getnchannels() == 1
            assert f.getsampwidth() == 2
            assert f.getframerate() == SAMPLE_RATE
            assert f.getnframes() > 0


def test_ensure_cues_is_idempotent(tmp_path):
    first = ensure_cues(tmp_path)
    stamps = {k: p.stat().st_mtime_ns for k, p in first.items()}
    second = ensure_cues(tmp_path)
    assert first == second
    assert stamps == {k: p.stat().st_mtime_ns for k, p in second.items()}
