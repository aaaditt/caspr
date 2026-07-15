from caspr.dictionary import build_initial_prompt


def test_empty_dictionary_gives_none():
    assert build_initial_prompt([]) is None


def test_terms_appear_in_prompt():
    prompt = build_initial_prompt(["caspr", "Aadit"])
    assert "caspr" in prompt
    assert "Aadit" in prompt


def test_terms_are_deduped_and_stripped():
    prompt = build_initial_prompt([" caspr ", "caspr", "", "  "])
    assert prompt.count("caspr") == 1


def test_prompt_stays_under_char_budget():
    terms = [f"someverylongterm{i}" for i in range(500)]
    prompt = build_initial_prompt(terms)
    # Whisper's initial_prompt window is ~224 tokens; keep a safe char budget.
    assert len(prompt) <= 600


def test_earlier_terms_win_when_truncating():
    terms = ["first_term"] + [f"filler{i}" for i in range(500)] + ["last_term"]
    prompt = build_initial_prompt(terms)
    assert "first_term" in prompt
    assert "last_term" not in prompt
