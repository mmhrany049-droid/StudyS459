"""Analytics orchestration: overview, topics, history, trends, weaknesses (spec 07).

Definitions (v1, documented):
- volume   = finalized question-instances (correct+wrong+unanswered+pending).
- coverage = distinct questions presented in FINISHED sessions / pool.
- accuracy = correct / (correct + wrong); pending is unknown, never counted.
- pool(node) = questions mapped to the node or any descendant (shared with
  the test engine's selection pool).
- In-progress sessions are excluded everywhere (nothing is final yet).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.analytics.metrics import (
    accuracy as calc_accuracy,
)
from app.analytics.metrics import (
    coverage as calc_coverage,
)
from app.analytics.metrics import (
    day_range,
    error_rate,
    rank_weaknesses,
    saturday_of,
    user_day,
    weakness_score,
)
from app.errors import AppError
from app.models import BookNode, NodeParityState, Question, TestSet
from app.repositories import analytics as repo
from app.repositories import books as book_repo
from app.repositories import tests as test_repo
from app.schemas.analytics import (
    BookProgressOut,
    BookTopicsOut,
    NodeProgressOut,
    OverviewOut,
    QuestionAttemptOut,
    QuestionHistoryOut,
    TopicRowOut,
    TrendPointOut,
    TrendsOut,
    WeaknessOut,
    WeaknessesOut,
)
from app.schemas.tests import TopicRef
from app.services.users import get_or_create_single_user


@dataclass
class _BookContext:
    book_id: int
    nodes: list[BookNode]
    by_id: dict[int, BookNode]
    children: dict[int | None, list[BookNode]]
    depth: dict[int, int]
    path: dict[int, str]
    pool: dict[int, set[int]]  # node_id -> question ids (node + descendants)
    parity: dict[int, str]  # node_id -> last_parity


@dataclass
class _Finals:
    buckets_per_q: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))
    sessions_of_q: dict[int, set[int]] = field(default_factory=lambda: defaultdict(set))
    session_started: dict[int, datetime] = field(default_factory=dict)
    session_ended: dict[int, datetime | None] = field(default_factory=dict)
    presented: set[int] = field(default_factory=set)  # qids in finished sessions


def _pair_buckets(db: Session, user_id: int) -> dict[tuple[int, int], str]:
    """Final bucket per (finished session, question) pair.

    Questions presented but never touched have no attempt rows and resolve
    to 'unanswered' via the membership list (never dropped).
    """
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


def _finals_of(db: Session, user_id: int) -> _Finals:
    out = _Finals()
    seen_pairs: set[tuple[int, int]] = set()
    for (sid, qid, answer, result, _answered, key, _diff, _book, started, ended) in repo.finals_rows(db, user_id):
        if result in ("correct", "wrong"):
            bucket = result  # stored verdict (auto or manual) wins
        elif answer is None:
            bucket = "unanswered"
        elif key is None:
            bucket = "pending"
        else:
            bucket = "correct" if answer == key else "wrong"
        out.buckets_per_q[qid].append(bucket)
        out.sessions_of_q[qid].add(sid)
        out.session_started[sid] = started
        out.session_ended[sid] = ended
        seen_pairs.add((sid, qid))
    for sid, qid in repo.finished_members(db, user_id):
        out.presented.add(qid)
        out.sessions_of_q[qid].add(sid)
        if (sid, qid) not in seen_pairs:
            # Presented in a finished session but never touched: unanswered.
            out.buckets_per_q[qid].append("unanswered")
    for s in repo.finished_sessions(db, user_id):
        out.session_started.setdefault(s.id, s.started_at)
        out.session_ended.setdefault(s.id, s.ended_at)
    return out


def _book_context(db: Session, *, user_id: int, book_id: int) -> _BookContext:
    nodes = book_repo.list_nodes_for_book(db, book_id)
    by_id = {n.id: n for n in nodes}
    children: dict[int | None, list[BookNode]] = defaultdict(list)
    for n in nodes:
        children[n.parent_id].append(n)
    depth: dict[int, int] = {}
    path: dict[int, str] = {}

    def walk(n: BookNode, d: int, trail: str) -> None:
        depth[n.id] = d
        path[n.id] = f"{trail} / {n.title}" if trail else n.title
        for c in children.get(n.id, []):
            walk(c, d + 1, path[n.id])

    for root in children.get(None, []):
        walk(root, 0, "")
    # Orphan-safe: unreachable nodes still get depth/path.
    for n in nodes:
        depth.setdefault(n.id, 0)
        path.setdefault(n.id, n.title)

    from sqlalchemy import select

    from app.models import QuestionTopicMap

    rows = db.execute(
        select(QuestionTopicMap.question_id, QuestionTopicMap.node_id)
        .join(Question, Question.id == QuestionTopicMap.question_id)
        .where(Question.book_id == book_id)
    ).all()
    direct: dict[int, set[int]] = defaultdict(set)
    for qid, nid in rows:
        direct[nid].add(qid)
    pool: dict[int, set[int]] = {}

    def pool_of(nid: int) -> set[int]:
        if nid in pool:
            return pool[nid]
        sub = set(direct.get(nid, set()))
        for c in children.get(nid, []):
            sub |= pool_of(c.id)
        pool[nid] = sub
        return sub

    for n in nodes:
        pool_of(n.id)

    parity_rows = db.execute(
        select(NodeParityState.node_id, NodeParityState.last_parity).where(
            NodeParityState.user_id == user_id,
            NodeParityState.node_id.in_([n.id for n in nodes]) if nodes else False,
        )
    ).all()
    return _BookContext(
        book_id=book_id, nodes=nodes, by_id=by_id, children=children,
        depth=depth, path=path, pool=pool,
        parity={nid: p for nid, p in parity_rows},
    )


def _counts(buckets: list[str]) -> dict[str, int]:
    return {
        "correct": buckets.count("correct"),
        "wrong": buckets.count("wrong"),
        "unanswered": buckets.count("unanswered"),
        "pending": buckets.count("pending"),
    }


def _topic_row(
    ctx: _BookContext, finals: _Finals, node: BookNode
) -> TopicRowOut:
    pool = ctx.pool.get(node.id, set())
    buckets: list[str] = []
    last_activity: datetime | None = None
    for qid in pool:
        buckets.extend(finals.buckets_per_q.get(qid, []))
        for sid in finals.sessions_of_q.get(qid, set()):
            ended = finals.session_ended.get(sid)
            if ended and (last_activity is None or ended > last_activity):
                last_activity = ended
    c = _counts(buckets)
    volume = len(buckets)
    attempted = len(pool & finals.presented)
    child_ids = {n.parent_id for n in ctx.nodes if n.parent_id is not None}
    return TopicRowOut(
        node_id=node.id,
        book_id=node.book_id,
        parent_id=node.parent_id,
        node_type=node.node_type,
        title=node.title,
        code=node.code,
        depth=ctx.depth.get(node.id, 0),
        path=ctx.path.get(node.id, node.title),
        is_leaf=node.id not in child_ids,
        total=len(pool),
        attempted=attempted,
        volume=volume,
        correct=c["correct"],
        wrong=c["wrong"],
        unanswered=c["unanswered"],
        pending=c["pending"],
        coverage=calc_coverage(attempted, len(pool)),
        accuracy=calc_accuracy(c["correct"], c["wrong"]),
        last_activity=last_activity,
        last_parity=ctx.parity.get(node.id),
    )


def overview(db: Session, *, user_id: int) -> OverviewOut:
    user = get_or_create_single_user(db, user_id)
    finals = _finals_of(db, user.id)
    books = book_repo.list_books(db)
    active_books = [b for b in books if (a := book_repo.get_activation(db, user.id, b.id)) and a.active]

    from app.models import TestSession as TS

    from sqlalchemy import func, select

    total_sessions = int(
        db.execute(select(func.count(TS.id)).where(TS.user_id == user.id)).scalar() or 0
    )
    finished = repo.finished_sessions(db, user.id)

    per_book: list[BookProgressOut] = []
    for book in books:
        ctx = _book_context(db, user_id=user.id, book_id=book.id)
        pool_all: set[int] = set()
        for s in ctx.pool.values():
            pool_all |= s
        buckets: list[str] = []
        last_activity: datetime | None = None
        for qid in pool_all:
            buckets.extend(finals.buckets_per_q.get(qid, []))
            for sid in finals.sessions_of_q.get(qid, set()):
                ended = finals.session_ended.get(sid)
                if ended and (last_activity is None or ended > last_activity):
                    last_activity = ended
        c = _counts(buckets)
        activation = book_repo.get_activation(db, user.id, book.id)
        per_book.append(
            BookProgressOut(
                book_id=book.id,
                title=book.title,
                active=bool(activation and activation.active),
                volume=len(buckets),
                correct=c["correct"],
                wrong=c["wrong"],
                unanswered=c["unanswered"],
                pending=c["pending"],
                accuracy=calc_accuracy(c["correct"], c["wrong"]),
                coverage=calc_coverage(len(pool_all & finals.presented), len(pool_all)),
                last_activity=last_activity,
            )
        )

    # Global scope = ACTIVE books only (documented).
    active_ids = {b.id for b in active_books}
    active_pool: set[int] = set()
    active_buckets: list[str] = []
    for book in active_books:
        ctx = _book_context(db, user_id=user.id, book_id=book.id)
        for qids in ctx.pool.values():
            for qid in qids:
                active_pool.add(qid)
    for qid in active_pool:
        active_buckets.extend(finals.buckets_per_q.get(qid, []))
    g = _counts(active_buckets)
    _ = active_ids  # pools already scoped via active_books contexts
    return OverviewOut(
        user_id=user.id,
        sessions_total=total_sessions,
        sessions_completed=len(finished),
        volume=len(active_buckets),
        correct=g["correct"],
        wrong=g["wrong"],
        unanswered=g["unanswered"],
        pending=g["pending"],
        accuracy=calc_accuracy(g["correct"], g["wrong"]),
        coverage=calc_coverage(len(active_pool & finals.presented), len(active_pool)),
        books=per_book,
    )


def book_topics(db: Session, *, user_id: int, book_id: int) -> BookTopicsOut:
    get_or_create_single_user(db, user_id)
    book = book_repo.get_book(db, book_id)
    if book is None:
        raise AppError("book_not_found", "کتاب یافت نشد.", status_code=404)
    ctx = _book_context(db, user_id=user_id, book_id=book_id)
    finals = _finals_of(db, user_id)
    return BookTopicsOut(
        book_id=book_id,
        topics=[_topic_row(ctx, finals, n) for n in ctx.nodes],
    )


def node_progress(db: Session, *, user_id: int, node_id: int) -> NodeProgressOut:
    get_or_create_single_user(db, user_id)
    node = book_repo.get_node(db, node_id)
    if node is None:
        raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
    ctx = _book_context(db, user_id=user_id, book_id=node.book_id)
    finals = _finals_of(db, user_id)
    kids = [n for n in ctx.nodes if n.parent_id == node_id]
    kids.sort(key=lambda n: (n.order_index, n.id))
    return NodeProgressOut(
        node=_topic_row(ctx, finals, node),
        children=[_topic_row(ctx, finals, k) for k in kids],
    )


def question_history(db: Session, *, user_id: int, question_id: int) -> QuestionHistoryOut:
    from sqlalchemy import select

    get_or_create_single_user(db, user_id)
    question = db.get(Question, question_id)
    if question is None:
        raise AppError("question_not_found", "سؤال یافت نشد.", status_code=404)
    test_set = db.get(TestSet, question.test_set_id)
    rows = repo.question_attempts(db, user_id=user_id, question_id=question_id)
    topics = test_repo.topics_for_questions(db, [question_id]).get(question_id, [])

    # Finals per session: rows are id-desc, so first row per session wins.
    seen_sessions: set[int] = set()
    finals: list[str] = []
    for a in rows:
        if a.session_id in seen_sessions:
            continue
        seen_sessions.add(a.session_id)
        if a.answer is None:
            finals.append("unanswered")
        elif a.result in ("correct", "wrong"):
            finals.append(a.result)
        elif question.answer_key is None:
            finals.append("pending")
        else:
            finals.append("correct" if a.answer == question.answer_key else "wrong")
    c = _counts(finals)
    return QuestionHistoryOut(
        question_id=question.id,
        book_id=question.book_id,
        test_set_id=question.test_set_id,
        test_set_title=test_set.title if test_set else "",
        sequence_no=question.sequence_no,
        difficulty=question.difficulty_level,
        has_answer_key=question.answer_key is not None,
        topics=[TopicRef(node_id=nid, title=title) for nid, title in topics],
        sessions_count=len(seen_sessions),
        attempt_count=len(rows),
        correct=c["correct"],
        wrong=c["wrong"],
        unanswered=c["unanswered"],
        pending=c["pending"],
        last_answer=rows[0].answer if rows else None,
        last_result=rows[0].result if rows else None,
        first_seen_at=min((a.answered_at for a in rows), default=None),
        last_seen_at=max((a.answered_at for a in rows), default=None),
        attempts=[
            QuestionAttemptOut(
                session_id=a.session_id,
                answer=a.answer,
                result=a.result,
                answered_at=a.answered_at,
                response_time_seconds=a.response_time_seconds,
            )
            for a in rows
        ],
    )


def trends(
    db: Session, *, user_id: int, days: int, group_by: str, today: datetime | None = None
) -> TrendsOut:
    user = get_or_create_single_user(db, user_id)
    if group_by not in ("day", "week"):
        raise AppError("invalid_group_by", "group_by باید day یا week باشد.", status_code=422)
    if not 1 <= days <= 365:
        raise AppError("invalid_days", "days باید بین ۱ تا ۳۶۵ باشد.", status_code=422)
    now = today or datetime.now()
    end_day = user_day(now.replace(tzinfo=None), user.timezone)
    buckets = day_range(end_day, days)
    finals = _finals_of(db, user.id)

    per_day: dict = {d: {"sessions": set(), "buckets": []} for d in buckets}
    for s in repo.finished_sessions(db, user.id):
        d = user_day(s.started_at, user.timezone)
        if d in per_day:
            per_day[d]["sessions"].add(s.id)
    # Attribute finals to the session's start day.
    session_day = {s.id: user_day(s.started_at, user.timezone) for s in repo.finished_sessions(db, user.id)}
    for (sid, _qid), bucket in _pair_buckets(db, user.id).items():
        d = session_day.get(sid)
        if d is None or d not in per_day:
            continue
        per_day[d]["buckets"].append(bucket)

    if group_by == "day":
        points = [
            TrendPointOut(
                period_start=d,
                sessions=len(per_day[d]["sessions"]),
                volume=len(per_day[d]["buckets"]),
                correct=(c := _counts(per_day[d]["buckets"]))["correct"],
                wrong=c["wrong"],
                unanswered=c["unanswered"],
                accuracy=calc_accuracy(c["correct"], c["wrong"]),
            )
            for d in buckets
        ]
    else:
        week_map: dict = {}
        for d in buckets:
            week_map.setdefault(saturday_of(d), []).append(d)
        points = []
        for saturday in sorted(week_map):
            sessions: set[int] = set()
            buckets_all: list[str] = []
            for d in week_map[saturday]:
                sessions |= per_day[d]["sessions"]
                buckets_all.extend(per_day[d]["buckets"])
            c = _counts(buckets_all)
            points.append(
                TrendPointOut(
                    period_start=saturday,
                    sessions=len(sessions),
                    volume=len(buckets_all),
                    correct=c["correct"],
                    wrong=c["wrong"],
                    unanswered=c["unanswered"],
                    accuracy=calc_accuracy(c["correct"], c["wrong"]),
                )
            )
    return TrendsOut(group_by=group_by, days=days, points=points)


def weaknesses(
    db: Session, *, user_id: int, limit: int, min_volume: int
) -> WeaknessesOut:
    user = get_or_create_single_user(db, user_id)
    if not 1 <= limit <= 100:
        raise AppError("invalid_limit", "limit باید بین ۱ تا ۱۰۰ باشد.", status_code=422)
    if min_volume < 1:
        raise AppError("invalid_min_volume", "min_volume باید حداقل ۱ باشد.", status_code=422)
    finals = _finals_of(db, user.id)
    rows: list[dict] = []
    for book in book_repo.list_books(db):
        activation = book_repo.get_activation(db, user.id, book.id)
        if not (activation and activation.active):
            continue  # actionable weaknesses come from ACTIVE books only
        ctx = _book_context(db, user_id=user.id, book_id=book.id)
        child_ids = {n.parent_id for n in ctx.nodes if n.parent_id is not None}
        for node in ctx.nodes:
            pool = ctx.pool.get(node.id, set())
            buckets: list[str] = []
            last_activity = None
            for qid in pool:
                buckets.extend(finals.buckets_per_q.get(qid, []))
                for sid in finals.sessions_of_q.get(qid, set()):
                    ended = finals.session_ended.get(sid)
                    if ended and (last_activity is None or ended > last_activity):
                        last_activity = ended
            c = _counts(buckets)
            volume = len(buckets)
            rows.append({
                "node_id": node.id,
                "book_id": book.id,
                "title": node.title,
                "path": ctx.path.get(node.id, node.title),
                "node_type": node.node_type,
                "is_leaf": node.id not in child_ids,
                "volume": volume,
                "correct": c["correct"],
                "wrong": c["wrong"],
                "unanswered": c["unanswered"],
                "error_rate": error_rate(c["correct"], c["wrong"]),
                "last_activity": last_activity,
                "last_parity": ctx.parity.get(node.id),
                "score": weakness_score(c["correct"], c["wrong"], c["unanswered"]),
            })
    ranked = rank_weaknesses(rows, min_volume=min_volume, limit=limit)
    return WeaknessesOut(items=[WeaknessOut(**{k: r[k] for k in (
        "node_id", "book_id", "title", "path", "node_type", "is_leaf", "volume",
        "correct", "wrong", "unanswered", "error_rate", "last_activity",
        "last_parity", "score")}) for r in ranked])
