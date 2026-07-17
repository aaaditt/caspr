from datetime import datetime, timedelta

from caspr.timefmt import rel_time

NOW = datetime(2026, 7, 18, 15, 0, 0)  # Saturday afternoon
NOW_TS = NOW.timestamp()


def ago(**kwargs) -> float:
    return (NOW - timedelta(**kwargs)).timestamp()


def test_just_now_boundary():
    assert rel_time(ago(seconds=44), NOW_TS) == "just now"
    assert rel_time(ago(seconds=45), NOW_TS) == "1 min ago"


def test_minutes_to_hours_boundary():
    assert rel_time(ago(minutes=59), NOW_TS) == "59 min ago"
    assert rel_time(ago(minutes=60), NOW_TS) == "1 h ago"
    assert rel_time(ago(hours=23), NOW_TS) == "23 h ago"


def test_yesterday_uses_calendar_date_beyond_24h():
    then = NOW - timedelta(hours=25)  # yesterday 14:00
    assert rel_time(then.timestamp(), NOW_TS) == "yesterday 14:00"


def test_days_ago_and_absolute_fallback():
    assert rel_time(ago(days=3), NOW_TS) == "3 days ago"
    assert rel_time(ago(days=10), NOW_TS) == "8 Jul"


def test_future_timestamps_clamp_to_just_now():
    assert rel_time(ago(seconds=-30), NOW_TS) == "just now"
