"""Pure analytics helpers: tz bucketing, ratios, weakness ranking (spec 07).

Framework-free. All datetimes in: naive UTC (DB convention). All days out:
user-timezone calendar dates (default Asia/Tehran, spec 13).
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


def user_day(dt_naive_utc: datetime, tz_name: str) -> date:
    """Calendar date of a naive-UTC instant in the user's timezone."""
    return dt_naive_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name)).date()


def day_range(end: date, days: int) -> list[date]:
    return [end - timedelta(days=i) for i in range(days - 1, -1, -1)]


def saturday_of(d: date) -> date:
    """Week start for the Iranian week (Saturday..Friday, spec 01)."""
    # Monday=0..Sunday=6; Saturday=5 -> days since Saturday, mod 7.
    return d - timedelta(days=(d.weekday() - 5) % 7)


def accuracy(correct: int, wrong: int) -> float | None:
    answered = correct + wrong
    return (correct / answered) if answered else None


def coverage(attempted: int, total: int) -> float | None:
    return (attempted / total) if total else None


def error_rate(correct: int, wrong: int) -> float | None:
    answered = correct + wrong
    return (wrong / answered) if answered else None


def weakness_score(correct: int, wrong: int, unanswered: int) -> float:
    """Higher = weaker. Wrong counts fully, unanswered counts half (spec 07
    signals: error rate + unanswered; pending is unknown, never counted)."""
    denom = correct + wrong + unanswered
    if not denom:
        return 0.0
    return (wrong + 0.5 * unanswered) / denom


def rank_weaknesses(rows: list[dict[str, Any]], *, min_volume: int, limit: int) -> list[dict[str, Any]]:
    """Sort: score desc -> unanswered desc -> recent activity first -> volume desc.

    last_activity None sorts as oldest (never active = no urgency signal).
    """
    eligible = [r for r in rows if r["volume"] >= min_volume and r["score"] > 0]

    def sort_key(r: dict[str, Any]) -> tuple:
        last = r.get("last_activity")
        # Recent first; None (never active) sorts last.
        recency = -last.timestamp() if last is not None else float("inf")
        return (-r["score"], -r["unanswered"], recency, -r["volume"])

    return sorted(eligible, key=sort_key)[:limit]
