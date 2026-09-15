"""Student State signals (spec 03/16, Phase 7).

Aggregates analytics + review + goals + homework + exams + schedule +
unfinished work into one snapshot. Consumed by candidate generation
(Phase 4's recommendation output) — the state -> recommendation link.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.analytics.metrics import user_day
from app.db import utcnow
from app.repositories import academic as academic_repo
from app.repositories import analytics as analytics_repo
from app.repositories import planner as planner_repo
from app.repositories import tests as test_repo
from app.services import analytics as analytics_service
from app.services.users import get_or_create_single_user


@dataclass
class StateSignals:
    weak_scores: dict[int, float] = field(default_factory=dict)
    ranked_weak_nodes: list[int] = field(default_factory=list)
    review_by_node: dict[int, dict[str, int]] = field(default_factory=dict)
    pending_reviews: int = 0
    open_tasks: int = 0
    overdue_tasks: int = 0
    pending_homework: int = 0
    done_homework: int = 0
    exam_count: int = 0


def get_signals(db: Session, *, user_id: int) -> StateSignals:
    user = get_or_create_single_user(db, user_id)
    today = user_day(utcnow().replace(tzinfo=None), user.timezone)

    weak_ranked = analytics_service.weaknesses(
        db, user_id=user.id, limit=100, min_volume=1).items
    review_by_node = _review_groups_by_node(db, user_id=user.id)
    pending_reviews = len(analytics_repo.pending_reviews(db, user.id))

    open_tasks = overdue = 0
    for t in planner_repo.list_tasks(db, user.id):
        if t.status not in ("planned", "in_progress"):
            continue
        open_tasks += 1
        if t.due_at is not None and user_day(t.due_at, user.timezone) < today:
            overdue += 1

    homework = academic_repo.list_homework(db, user.id, status=None)
    pending_homework = sum(1 for h in homework if h.status == "pending")
    done_homework = sum(1 for h in homework if h.status == "done")
    exam_count = len(academic_repo.list_exams(db, user.id))

    return StateSignals(
        weak_scores={w.node_id: w.score for w in weak_ranked},
        ranked_weak_nodes=[w.node_id for w in weak_ranked],
        review_by_node=review_by_node,
        pending_reviews=pending_reviews,
        open_tasks=open_tasks,
        overdue_tasks=overdue,
        pending_homework=pending_homework,
        done_homework=done_homework,
        exam_count=exam_count,
    )


def _review_groups_by_node(db: Session, *, user_id: int) -> dict[int, dict[str, int]]:
    from collections import defaultdict

    groups: dict[int, dict[str, int]] = defaultdict(lambda: {"total": 0, "high": 0})
    pending = analytics_repo.pending_reviews(db, user_id)
    qids = [r.entity_id for r in pending if r.entity_type == "question"]
    topics = test_repo.topics_for_questions(db, qids)
    prio = {r.entity_id: r.priority for r in pending if r.entity_type == "question"}
    for qid in qids:
        for nid, _title in topics.get(qid, []):
            groups[nid]["total"] += 1
            if prio.get(qid) == "high":
                groups[nid]["high"] += 1
    return groups


def today_str(db: Session, *, user_id: int) -> str:
    """Today's date in the user's timezone (ISO)."""
    user = get_or_create_single_user(db, user_id)
    today: date = user_day(utcnow().replace(tzinfo=None), user.timezone)
    return today.isoformat()
