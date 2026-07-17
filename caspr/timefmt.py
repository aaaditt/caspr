"""Human-relative timestamps for the history and home views."""

from __future__ import annotations

import time
from datetime import date, datetime


def rel_time(ts: float, now: float | None = None) -> str:
    """"just now" / "N min ago" / "N h ago" / "yesterday HH:MM" / "N days ago" / "3 Jun"."""
    now = time.time() if now is None else now
    delta = max(0.0, now - ts)
    if delta < 45:
        return "just now"
    if delta < 3600:
        return f"{max(1, int(delta // 60))} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} h ago"
    then = datetime.fromtimestamp(ts)
    days_apart = (date.fromtimestamp(now) - then.date()).days
    if days_apart == 1:
        return f"yesterday {then:%H:%M}"
    if days_apart < 7:
        return f"{days_apart} days ago"
    return f"{then.day} {then:%b}"
