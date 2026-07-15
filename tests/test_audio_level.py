import numpy as np

from caspr.audio import meter_level


def test_silence_is_zero():
    block = np.zeros(1600, dtype=np.float32)
    assert meter_level(block) == 0.0


def test_full_scale_sine_is_near_one():
    t = np.linspace(0, 1, 16000, dtype=np.float32)
    block = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    assert meter_level(block) > 0.95


def test_quiet_signal_between_zero_and_loud():
    t = np.linspace(0, 1, 16000, dtype=np.float32)
    loud = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    quiet = (loud * 0.05).astype(np.float32)
    assert 0.0 < meter_level(quiet) < meter_level(loud)


def test_clipped_signal_capped_at_one():
    block = np.full(1600, 2.0, dtype=np.float32)  # beyond full scale
    assert meter_level(block) == 1.0
