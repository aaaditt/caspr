from pathlib import Path

import numpy as np
import pytest

from caspr.audio import load_wav_mono16k

FIXTURE = Path(__file__).parent / "fixtures" / "testing_one_two_three.wav"


def test_load_wav_fixture():
    audio = load_wav_mono16k(FIXTURE)
    assert audio.dtype == np.float32
    assert audio.ndim == 1
    assert len(audio) > 16000  # more than a second of speech
    assert float(np.abs(audio).max()) <= 1.0


@pytest.mark.slow
def test_transcribes_fixture_wav():
    from caspr.stt import Transcriber

    audio = load_wav_mono16k(FIXTURE)
    transcriber = Transcriber(model_name="tiny", device="cpu")
    result = transcriber.transcribe(audio)
    text = result.text.lower()
    # Whisper may render numbers as words or digits ("one two three" / "1, 2, 3")
    assert "testing" in text
    assert ("one" in text and "three" in text) or ("1" in text and "3" in text)
