from caspr.live_typing import LiveTypingSession


class FakeTranscriber:
    def __init__(self, hypotheses):
        self._hyps = list(hypotheses)

    def feed(self, block):
        return self._hyps.pop(0) if self._hyps else None


def _session(hypotheses):
    typed_calls = []
    backspace_calls = []
    session = LiveTypingSession(
        FakeTranscriber(hypotheses),
        type_text=typed_calls.append,
        backspace=backspace_calls.append,
    )
    return session, typed_calls, backspace_calls


def test_applies_a_diff_for_each_new_hypothesis():
    session, typed, backspaces = _session(["meet", "meet at"])
    session.feed_block("block1")
    session.feed_block("block2")
    session.finish()
    session.run()
    assert typed == ["meet", " at"]
    assert backspaces == [0, 0]
    assert session.typed_text == "meet at"


def test_unchanged_hypothesis_is_a_noop():
    session, typed, backspaces = _session(["hello", None, "hello"])
    session.feed_block("b1")
    session.feed_block("b2")
    session.feed_block("b3")
    session.finish()
    session.run()
    assert typed == ["hello"]  # only the first, real change


def test_finish_leaves_typed_text_on_screen():
    session, typed, backspaces = _session(["hi"])
    session.feed_block("b1")
    session.finish()
    session.run()
    assert session.typed_text == "hi"
    assert backspaces == [0]  # no erasure on a normal finish


def test_cancel_erases_everything_typed_this_session():
    session, typed, backspaces = _session(["hello world"])
    session.feed_block("b1")
    session.cancel()
    session.run()
    assert backspaces[-1] == len("hello world")
    assert session.typed_text == ""


def test_cancel_with_nothing_typed_yet_does_not_backspace():
    session, typed, backspaces = _session([])
    session.cancel()
    session.run()
    assert backspaces == []
