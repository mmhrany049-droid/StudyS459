"""Unit tests: pure analytics helpers (spec 07)."""

from datetime import date, datetime

from app.analytics.metrics import (
    accuracy,
    coverage,
    day_range,
    rank_weaknesses,
    saturday_of,
    user_day,
    weakness_score,
)


def test_user_day_tehran_boundary() -> None:
    # September: Tehran = UTC+3:30 (no DST).
    assert user_day(datetime(2026, 9, 14, 20, 0, 0), "Asia/Tehran") == date(2026, 9, 14)
    assert user_day(datetime(2026, 9, 14, 21, 0, 0), "Asia/Tehran") == date(2026, 9, 15)


def test_saturday_week_start() -> None:
    assert saturday_of(date(2026, 9, 12)) == date(2026, 9, 12)  # Saturday itself
    assert saturday_of(date(2026, 9, 13)) == date(2026, 9, 12)  # Sunday
    assert saturday_of(date(2026, 9, 18)) == date(2026, 9, 12)  # Friday
    assert saturday_of(date(2026, 9, 19)) == date(2026, 9, 19)  # next Saturday


def test_day_range() -> None:
    assert day_range(date(2026, 9, 14), 3) == [
        date(2026, 9, 12), date(2026, 9, 13), date(2026, 9, 14)]


def test_ratios() -> None:
    assert accuracy(3, 1) == 0.75
    assert accuracy(0, 0) is None
    assert coverage(2, 4) == 0.5
    assert coverage(0, 0) is None  # empty pool: undefined, not zero


def test_weakness_score_weights() -> None:
    assert weakness_score(0, 2, 0) == 1.0
    assert weakness_score(1, 1, 0) == 0.5
    assert weakness_score(0, 0, 2) == 0.5  # unanswered counts half
    assert weakness_score(5, 0, 0) == 0.0
    assert weakness_score(0, 0, 0) == 0.0


def test_rank_weaknesses_order_and_filters() -> None:
    rows = [
        {"volume": 10, "correct": 9, "wrong": 1, "unanswered": 0,
         "last_activity": datetime(2026, 9, 14), "score": weakness_score(9, 1, 0)},
        {"volume": 5, "correct": 0, "wrong": 5, "unanswered": 0,
         "last_activity": datetime(2026, 9, 10), "score": weakness_score(0, 5, 0)},
        {"volume": 2, "correct": 0, "wrong": 2, "unanswered": 0,
         "last_activity": datetime(2026, 9, 14), "score": weakness_score(0, 2, 0)},
        {"volume": 8, "correct": 8, "wrong": 0, "unanswered": 0,
         "last_activity": datetime(2026, 9, 14), "score": 0.0},  # all correct: hidden
    ]
    ranked = rank_weaknesses(rows, min_volume=3, limit=10)
    assert [r["volume"] for r in ranked] == [5, 10]  # score desc; tiny + perfect out
    ranked = rank_weaknesses(rows, min_volume=1, limit=1)
    assert [r["volume"] for r in ranked] == [2]  # limit honored (recent first)


def test_rank_recency_tiebreak() -> None:
    a = {"volume": 4, "correct": 2, "wrong": 2, "unanswered": 0,
         "last_activity": datetime(2026, 9, 1), "score": 0.5}
    b = {**a, "last_activity": datetime(2026, 9, 14)}
    c = {**a, "last_activity": None}
    assert rank_weaknesses([a, b, c], min_volume=1, limit=10) == [b, a, c]
