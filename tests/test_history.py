from caspr.history import History


def test_add_and_recent_roundtrip(tmp_path):
    h = History(tmp_path / "h.db")
    h.add("raw one", "final one", 0.5, 1.0)
    h.add("raw two", "final two", 0.4, 0.9)
    rows = h.recent()
    assert [r.final_text for r in rows] == ["final two", "final one"]  # newest first
    assert rows[0].raw_text == "raw two"
    assert rows[0].infer_s == 0.4


def test_delete(tmp_path):
    h = History(tmp_path / "h.db")
    row_id = h.add("a", "b", 0.1, 0.2)
    h.delete(row_id)
    assert h.recent() == []


def test_persists_across_instances(tmp_path):
    History(tmp_path / "h.db").add("a", "kept", 0.1, 0.2)
    assert History(tmp_path / "h.db").recent()[0].final_text == "kept"


def test_stats_counts_words_and_latency(tmp_path):
    h = History(tmp_path / "h.db")
    h.add("raw", "hello world", 0.2, 1.0)
    h.add("raw", "one two three", 0.2, 2.0)
    s = h.stats()
    assert s.today_count == 2  # added just now, so today
    assert s.total_words == 5
    assert s.avg_total_s == 1.5


def test_stats_empty_db(tmp_path):
    s = History(tmp_path / "h.db").stats()
    assert (s.today_count, s.total_words, s.avg_total_s) == (0, 0, 0.0)


def test_recent_respects_limit(tmp_path):
    h = History(tmp_path / "h.db")
    for i in range(5):
        h.add(f"r{i}", f"f{i}", 0.1, 0.2)
    assert len(h.recent(limit=3)) == 3
