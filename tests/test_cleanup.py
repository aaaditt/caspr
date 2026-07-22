"""AI cleanup stage: prompt assembly + resilient fallback.

The Groq network call is injected as `complete` so these tests never hit the
network; the contract under test is the pure prompt-building and the
never-lose-words fallback behaviour.
"""

from caspr.cleanup import build_cleanup_messages, clean_text
from caspr.config import Config


def test_messages_have_system_and_user_roles():
    msgs = build_cleanup_messages("hello", recent=[], glossary=[], tone="balanced")
    assert [m["role"] for m in msgs] == ["system", "user"]


def test_system_prompt_describes_self_correction():
    msgs = build_cleanup_messages("hi", recent=[], glossary=[], tone="balanced")
    system = msgs[0]["content"].lower()
    # The headline behaviour: honour spoken retractions, drop the retracted words.
    assert "correct" in system
    assert "only" in system and "cleaned text" in system


def test_messages_include_self_correction_when_smart_correct_on():
    msgs = build_cleanup_messages(
        "x", recent=[], glossary=[], tone="balanced", smart_correct=True
    )
    system = msgs[0]["content"].lower()
    assert "scratch that" in system or "never mind" in system


def test_messages_omit_self_correction_when_smart_correct_off():
    msgs = build_cleanup_messages(
        "x", recent=[], glossary=[], tone="balanced", smart_correct=False
    )
    system = msgs[0]["content"].lower()
    assert "scratch that" not in system
    assert "preserve" in system  # told to keep every stated value


def test_clean_text_passes_smart_correct_flag_from_cfg():
    cfg = Config(groq_api_key="gsk_x", smart_correct=False)
    captured = {}

    def capture(messages, cfg):
        captured["system"] = messages[0]["content"].lower()
        return "ok"

    clean_text("raw", recent=[], glossary=[], tone="balanced", cfg=cfg, complete=capture)
    assert "scratch that" not in captured["system"]


def test_user_message_carries_tone_glossary_recent_and_raw():
    msgs = build_cleanup_messages(
        "meet at 6:30",
        recent=["See you Monday.", "Thanks Aadit."],
        glossary=["Aadit", "caspr"],
        tone="casual",
    )
    user = msgs[1]["content"]
    assert "casual" in user
    assert "Aadit" in user and "caspr" in user
    assert "See you Monday." in user
    assert "meet at 6:30" in user


def test_clean_text_returns_model_output_on_success():
    cfg = Config(groq_api_key="gsk_x")
    out = clean_text(
        "meet at 5:30 actually no 6:30",
        recent=[],
        glossary=[],
        tone="balanced",
        cfg=cfg,
        complete=lambda messages, cfg: "Let's meet at 6:30.",
    )
    assert out == "Let's meet at 6:30."


def test_clean_text_falls_back_to_raw_when_disabled():
    cfg = Config(cleanup_enabled=False, groq_api_key="gsk_x")
    calls = []
    out = clean_text(
        "raw text",
        recent=[],
        glossary=[],
        tone="balanced",
        cfg=cfg,
        complete=lambda m, c: calls.append(1) or "cleaned",
    )
    assert out == "raw text"
    assert calls == []  # never even attempted


def test_clean_text_falls_back_to_raw_when_no_api_key():
    cfg = Config(groq_api_key="   ")
    out = clean_text(
        "raw text", recent=[], glossary=[], tone="balanced", cfg=cfg,
        complete=lambda m, c: "cleaned",
    )
    assert out == "raw text"


def test_clean_text_falls_back_to_raw_on_exception():
    cfg = Config(groq_api_key="gsk_x")

    def boom(messages, cfg):
        raise RuntimeError("groq down")

    out = clean_text(
        "raw text", recent=[], glossary=[], tone="balanced", cfg=cfg, complete=boom
    )
    assert out == "raw text"


def test_clean_text_falls_back_to_raw_on_empty_output():
    cfg = Config(groq_api_key="gsk_x")
    out = clean_text(
        "raw text", recent=[], glossary=[], tone="balanced", cfg=cfg,
        complete=lambda m, c: "   ",
    )
    assert out == "raw text"


def test_clean_text_truncates_recent_to_context_count():
    cfg = Config(groq_api_key="gsk_x", cleanup_context_count=3)
    captured = {}

    def capture(messages, cfg):
        captured["user"] = messages[1]["content"]
        return "ok"

    recent = [f"line{i}" for i in range(10)]  # caller passes most-recent-first
    clean_text("raw", recent=recent, glossary=[], tone="balanced", cfg=cfg, complete=capture)
    user = captured["user"]
    assert "line0" in user and "line1" in user and "line2" in user
    assert "line3" not in user  # only the first 3 (most recent) survive
