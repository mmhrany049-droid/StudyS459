"""Unit tests: pure selection/scoring/expiry rules (spec 06/13)."""

import random
from datetime import datetime, timedelta

import pytest

from app.domain.test_selection import (
    InsufficientQuestions,
    PoolQuestion,
    count_by_parity,
    deadline,
    filter_pool,
    is_expired,
    score_session,
    select_question_ids,
    suggest_parity,
)

POOL = [PoolQuestion(id=i, sequence_no=i) for i in range(1, 11)]  # seq 1..10


def test_filter_range_only() -> None:
    got = filter_pool(POOL, sequence_from=3, sequence_to=5)
    assert [q.sequence_no for q in got] == [3, 4, 5]


def test_filter_open_ended_ranges() -> None:
    assert [q.sequence_no for q in filter_pool(POOL, sequence_from=9)] == [9, 10]
    assert [q.sequence_no for q in filter_pool(POOL, sequence_to=2)] == [1, 2]
    assert len(filter_pool(POOL)) == 10


def test_filter_parity() -> None:
    assert [q.sequence_no for q in filter_pool(POOL, parity="odd")] == [1, 3, 5, 7, 9]
    assert [q.sequence_no for q in filter_pool(POOL, parity="even")] == [2, 4, 6, 8, 10]
    assert len(filter_pool(POOL, parity="any")) == 10


def test_filter_range_and_parity_combined() -> None:
    got = filter_pool(POOL, sequence_from=4, sequence_to=9, parity="odd")
    assert [q.sequence_no for q in got] == [5, 7, 9]


def test_count_by_parity() -> None:
    assert count_by_parity(POOL) == {"odd": 5, "even": 5}
    assert count_by_parity([]) == {"odd": 0, "even": 0}


def test_select_exact_pool() -> None:
    picked = select_question_ids(POOL, 10, rng=random.Random(1))
    assert sorted(picked) == list(range(1, 11))


def test_select_no_duplicates_and_subset() -> None:
    picked = select_question_ids(POOL, 6, rng=random.Random(7))
    assert len(set(picked)) == 6
    assert set(picked) <= set(range(1, 11))


def test_select_seeded_is_deterministic() -> None:
    a = select_question_ids(POOL, 5, rng=random.Random(459))
    b = select_question_ids(POOL, 5, rng=random.Random(459))
    assert a == b


def test_select_insufficient_raises_with_counts() -> None:
    pool = filter_pool(POOL, sequence_from=1, sequence_to=4, parity="odd")  # seq 1,3
    with pytest.raises(InsufficientQuestions) as e:
        select_question_ids(pool, 3)
    assert (e.value.requested, e.value.available) == (3, 2)
    assert (e.value.available_odd, e.value.available_even) == (2, 0)


def test_suggest_parity() -> None:
    assert suggest_parity("odd") == "even"
    assert suggest_parity("even") == "odd"
    assert suggest_parity(None) is None


def test_expiry_boundaries() -> None:
    start = datetime(2026, 9, 14, 12, 0, 0)
    assert deadline(start, 60) == start + timedelta(seconds=60)
    assert is_expired(start, 60, start + timedelta(seconds=59)) is False
    assert is_expired(start, 60, start + timedelta(seconds=60)) is True  # boundary counts
    assert is_expired(start, 60, start + timedelta(seconds=61)) is True


def test_score_all_correct() -> None:
    score = score_session([1, 2], {1: "a", 2: "b"}, {1: "a", 2: "b"})
    assert (score.totals.correct, score.totals.wrong) == (2, 0)
    assert score.totals.unanswered == 0 and score.totals.pending == 0
    assert score.accuracy == 1.0


def test_score_mixed_and_accuracy() -> None:
    score = score_session([1, 2, 3, 4], {1: "a", 2: "b", 3: "c", 4: "d"},
                          {1: "a", 2: "x"})
    assert (score.totals.correct, score.totals.wrong, score.totals.unanswered) == (1, 1, 2)
    assert score.accuracy == 0.5


def test_score_null_answer_is_unanswered() -> None:
    score = score_session([1], {1: "a"}, {1: None})
    assert score.totals.unanswered == 1
    assert score.accuracy is None


def test_score_missing_key_is_pending_never_guessed() -> None:
    score = score_session([1, 2], {1: None, 2: "b"}, {1: "a", 2: "b"})
    assert score.totals.pending == 1
    assert score.totals.correct == 1
    assert score.accuracy == 1.0  # pending excluded


def test_score_nothing_answered_accuracy_none() -> None:
    score = score_session([1, 2], {1: "a", 2: "b"}, {})
    assert score.accuracy is None
    assert score.totals.unanswered == 2


def test_stored_verdict_wins_over_recompute() -> None:
    # Manual correction of a keyless question must survive recomputation.
    score = score_session([1], {1: None}, {1: "a"}, {1: "correct"})
    assert score.totals.correct == 1 and score.totals.pending == 0
    assert score.accuracy == 1.0
    assert score.buckets == {1: "correct"}


def test_stored_wrong_respected() -> None:
    score = score_session([1], {1: "a"}, {1: "a"}, {1: "wrong"})
    assert score.totals.wrong == 1
    assert score.verdicts == {1: "wrong"}


def test_result_invariant() -> None:
    score = score_session([1, 2, 3], {1: "a", 2: None, 3: "c"}, {1: "a", 2: "x"})
    t = score.totals
    assert t.correct + t.wrong + t.unanswered + t.pending == 3
