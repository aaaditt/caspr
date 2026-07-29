from caspr.diff import compute_correction


def test_identical_text_is_a_noop():
    assert compute_correction("meet at 6:30", "meet at 6:30") == (0, "")


def test_appends_new_words_to_empty_typed():
    assert compute_correction("", "hello") == (0, "hello")


def test_appends_new_words_after_existing_typed():
    assert compute_correction("meet at", "meet at six") == (0, " six")


def test_corrects_a_tail_word():
    backspaces, insert = compute_correction("meet at six thirty", "meet at 6:30")
    assert backspaces == len(" six thirty")
    assert insert == " 6:30"


def test_full_replacement_when_no_shared_prefix():
    backspaces, insert = compute_correction("foo bar", "baz qux")
    assert backspaces == len("foo bar")
    assert insert == "baz qux"


def test_backspace_count_never_exceeds_typed_length():
    backspaces, _ = compute_correction("hi", "a completely different and much longer sentence")
    assert backspaces <= len("hi")
