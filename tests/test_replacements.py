from caspr.replacements import apply_replacements


def test_whole_word_case_insensitive():
    assert apply_replacements("hi adit and Adit", {"Adit": "Aadit"}) == "hi Aadit and Aadit"


def test_partial_words_untouched():
    assert apply_replacements("Aditya said hi", {"Adit": "Aadit"}) == "Aditya said hi"


def test_empty_rules_identity():
    assert apply_replacements("hello", {}) == "hello"


def test_multiple_rules():
    out = apply_replacements("adit met rahul", {"adit": "Aadit", "rahul": "Rahul"})
    assert out == "Aadit met Rahul"
