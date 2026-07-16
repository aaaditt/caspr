from caspr.spellcheck import flag_unknown_words


def _flagged_words(text, terms=(), threshold=3.0):
    return [text[s:e] for s, e in flag_unknown_words(text, terms, threshold)]


def test_rare_name_is_flagged():
    assert _flagged_words("hello Aadit here") == ["Aadit"]


def test_common_words_not_flagged():
    assert _flagged_words("we scheduled a meeting for testing tomorrow") == []


def test_dictionary_suppresses_flag():
    assert _flagged_words("hello Aadit here", terms=["aadit"]) == []


def test_contractions_and_numbers_ignored():
    assert _flagged_words("don't send 42 files") == []


def test_spans_are_correct_offsets():
    text = "ok Aadit ok"
    ((s, e),) = flag_unknown_words(text, [])
    assert text[s:e] == "Aadit"
