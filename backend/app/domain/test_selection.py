"""Pure test-engine rules: pool filtering, sampling, scoring, expiry (spec 06/13).

Framework-free. All randomness flows through an injectable `random.Random`
so tests can be deterministic; production passes None (thread-safe default).
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

ODD = "odd"
EVEN = "even"
ANY = "any"
PARITIES: tuple[str, ...] = (ODD, EVEN, ANY)


class InsufficientQuestions(Exception):
    """Raised when the eligible pool is smaller than the requested count."""

    def __init__(self, *, requested: int, available: int, available_odd: int, available_even: int) -> None:
        self.requested = requested
        self.available = available
        self.available_odd = available_odd
        self.available_even = available_even
        super().__init__(f"need {requested}, have {available}")


@dataclass(frozen=True)
class PoolQuestion:
    id: int
    sequence_no: int


def filter_pool(
    questions: list[PoolQuestion],
    *,
    sequence_from: int | None = None,
    sequence_to: int | None = None,
    parity: str = ANY,
) -> list[PoolQuestion]:
    """Apply range + odd/even filters (spec 06 rules 1-4)."""
    out = []
    for q in questions:
        if sequence_from is not None and q.sequence_no < sequence_from:
            continue
        if sequence_to is not None and q.sequence_no > sequence_to:
            continue
        if parity == ODD and q.sequence_no % 2 == 0:
            continue
        if parity == EVEN and q.sequence_no % 2 == 1:
            continue
        out.append(q)
    return out


def count_by_parity(questions: list[PoolQuestion]) -> dict[str, int]:
    odd = sum(1 for q in questions if q.sequence_no % 2 == 1)
    return {"odd": odd, "even": len(questions) - odd}


def select_question_ids(
    pool: list[PoolQuestion], count: int, *, rng: random.Random | None = None
) -> list[int]:
    """Random sample without replacement (spec 06 rule 5).

    Raises InsufficientQuestions instead of returning a partial session
    (spec 06 rule 6) — the caller turns this into a clear message.
    """
    if len(pool) < count:
        by_parity = count_by_parity(pool)
        raise InsufficientQuestions(
            requested=count,
            available=len(pool),
            available_odd=by_parity["odd"],
            available_even=by_parity["even"],
        )
    rng = rng or random.Random()
    return [q.id for q in rng.sample(sorted(pool, key=lambda q: q.id), count)]


def suggest_parity(last_parity: str | None) -> str | None:
    """Opposite of the last used parity; None when there is no history."""
    if last_parity == ODD:
        return EVEN
    if last_parity == EVEN:
        return ODD
    return None


def deadline(started_at: datetime, time_limit_seconds: int) -> datetime:
    return started_at + timedelta(seconds=time_limit_seconds)


def is_expired(started_at: datetime, time_limit_seconds: int, now: datetime) -> bool:
    return now >= deadline(started_at, time_limit_seconds)


@dataclass(frozen=True)
class ScoreResult:
    correct: int
    wrong: int
    unanswered: int
    pending: int


@dataclass(frozen=True)
class SessionScore:
    totals: ScoreResult
    verdicts: dict[int, str | None]  # question_id -> 'correct' | 'wrong' | None
    buckets: dict[int, str]  # question_id -> correct | wrong | unanswered | pending
    accuracy: float | None  # correct / (correct + wrong); None when nothing answered


def score_session(
    question_ids: list[int],
    answer_keys: dict[int, str | None],
    latest_answers: dict[int, str | None],
    latest_results: dict[int, str | None] | None = None,
) -> SessionScore:
    """Score from latest attempts.

    - A STORED verdict (auto at finish, or manual correction) is authoritative
      and always wins — recomputation must never override a correction.
    - Otherwise: no/NULL answer -> unanswered; missing key -> pending
      (never guessed); else compare with the key.
    """
    stored = latest_results or {}
    correct = wrong = unanswered = pending = 0
    verdicts: dict[int, str | None] = {}
    buckets: dict[int, str] = {}
    for qid in question_ids:
        if stored.get(qid) in ("correct", "wrong"):
            bucket = stored[qid]
            assert bucket in ("correct", "wrong")
            verdicts[qid] = bucket
        elif qid not in latest_answers or latest_answers[qid] is None:
            bucket = "unanswered"
            verdicts[qid] = None
        elif answer_keys.get(qid) is None:
            bucket = "pending"
            verdicts[qid] = None
        elif latest_answers[qid] == answer_keys[qid]:
            bucket = "correct"
            verdicts[qid] = "correct"
        else:
            bucket = "wrong"
            verdicts[qid] = "wrong"
        buckets[qid] = bucket
        if bucket == "correct":
            correct += 1
        elif bucket == "wrong":
            wrong += 1
        elif bucket == "unanswered":
            unanswered += 1
        else:
            pending += 1
    answered = correct + wrong
    return SessionScore(
        totals=ScoreResult(correct=correct, wrong=wrong, unanswered=unanswered, pending=pending),
        verdicts=verdicts,
        buckets=buckets,
        accuracy=(correct / answered) if answered else None,
    )
