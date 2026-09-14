"""Final buckets per (finished session, question) pair (shared).

Stored verdicts (auto at finish, manual via corrections) win over recompute.
Questions presented but never touched have no attempt rows and resolve to
'unanswered' via the membership list (never dropped).
"""

from sqlalchemy.orm import Session

from app.repositories import analytics as repo


def pair_buckets(db: Session, user_id: int) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    for (sid, qid, answer, result, _at, key, *_rest) in repo.finals_rows(db, user_id):
        if result in ("correct", "wrong"):
            out[(sid, qid)] = result
        elif answer is None:
            out[(sid, qid)] = "unanswered"
        elif key is None:
            out[(sid, qid)] = "pending"
        else:
            out[(sid, qid)] = "correct" if answer == key else "wrong"
    for sid, qid in repo.finished_members(db, user_id):
        out.setdefault((sid, qid), "unanswered")
    return out
