"""Review population: wrong + unanswered finals become candidates (spec 03).

- Called from session finish / manual correction (same transaction).
- One open row per (question, reason): re-failing an already-queued
  question does not spam the queue.
"""

from sqlalchemy.orm import Session

from app.repositories import analytics as repo


def populate_for_session(
    db: Session, *, user_id: int, buckets: dict[int, str]
) -> int:
    added = 0
    for qid, bucket in buckets.items():
        if bucket == "wrong":
            reason, priority = "wrong", "high"
        elif bucket == "unanswered":
            reason, priority = "unanswered", "normal"
        else:
            continue
        if repo.open_review_exists(
            db, user_id=user_id, entity_type="question", entity_id=qid, reason=reason
        ):
            continue
        repo.add_review(
            db, user_id=user_id, entity_type="question", entity_id=qid,
            reason=reason, priority=priority,
        )
        added += 1
    return added


def populate_for_correction(
    db: Session, *, user_id: int, question_id: int, result: str
) -> bool:
    if result != "wrong":
        return False
    if repo.open_review_exists(
        db, user_id=user_id, entity_type="question", entity_id=question_id, reason="wrong"
    ):
        return False
    repo.add_review(
        db, user_id=user_id, entity_type="question", entity_id=question_id,
        reason="wrong", priority="high",
    )
    return True
