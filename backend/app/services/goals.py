"""Weekly goals + candidate tasks (spec 02/08, Phase 4).

Progress is always DERIVED from finalized attempts (never stored counters):
- count item: week volume within scope vs target number of questions.
- topic item: week coverage of the node pool vs target coverage fraction.
- week totals count every instance ONCE even if several items overlap
  (spec 13: no double counting).

Candidate tasks are computed suggestions (not persisted; tasks arrive in
Phase 5). Topic goals outrank count goals; inactive books never produce
candidates (consistent with weaknesses).
"""

import math
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.analytics.context import BookContext, build_book_context
from app.analytics.finals import pair_buckets
from app.analytics.metrics import (
    coverage as calc_coverage,
)
from app.analytics.metrics import normalize_week, week_window_utc
from app.errors import AppError
from app.models import WeeklyGoal
from app.repositories import analytics as analytics_repo
from app.repositories import books as book_repo
from app.repositories import goals as repo
from app.schemas.goals import (
    CandidateTaskOut,
    CandidateTasksOut,
    GoalItemIn,
    GoalItemOut,
    ItemProgressOut,
    WeekGoalCreate,
    WeekGoalOut,
    WeekGoalPatch,
)
from app.services.users import get_or_create_single_user

SOURCE_BASE_SCORE = {
    "goal_topic": 0.50,
    "review": 0.30,
    "weakness": 0.25,
    "goal_count": 0.20,
}
PARITY_FA = {"odd": "فرد", "even": "زوج", "any": "آزاد"}


def parse_week(week: str) -> tuple[date, date]:
    try:
        day = date.fromisoformat(week)
    except ValueError:
        raise AppError("invalid_week", "قالب هفته باید YYYY-MM-DD باشد.", status_code=422)
    return normalize_week(day)


def _validate_item(db: Session, item: GoalItemIn) -> dict:
    """Existence + consistency checks. Returns normalized scope dict."""
    node = book_repo.get_node(db, item.node_id) if item.node_id else None
    if item.node_id and node is None:
        raise AppError("node_not_found", "گره یافت نشد.", status_code=404)
    book = book_repo.get_book(db, item.book_id) if item.book_id else None
    if item.book_id and book is None:
        raise AppError("book_not_found", "کتاب یافت نشد.", status_code=404)
    subject = book_repo.get_subject(db, item.subject_id) if item.subject_id else None
    if item.subject_id and subject is None:
        raise AppError("subject_not_found", "درس یافت نشد.", status_code=404)
    if node and book and node.book_id != book.id:
        raise AppError("invalid_goal_item", "گره متعلق به این کتاب نیست.", status_code=422)
    scope_book_id = node.book_id if node else (book.id if book else None)
    if subject and scope_book_id:
        scope_book = book_repo.get_book(db, scope_book_id)
        assert scope_book is not None
        if scope_book.subject_id != subject.id:
            raise AppError("invalid_goal_item", "کتاب متعلق به این درس نیست.", status_code=422)
    if item.goal_type == "topic":
        if node is None:
            raise AppError("invalid_goal_item", "هدف موضوعی نیاز به node_id دارد.", status_code=422)
        if not 0 < item.target_value <= 1:
            raise AppError(
                "invalid_goal_item", "هدف پوششی موضوع باید بین ۰ تا ۱ باشد.", status_code=422
            )
    else:
        if item.target_value < 1 or item.target_value != int(item.target_value):
            raise AppError(
                "invalid_goal_item", "هدف تعداد باید عدد صحیح مثبت باشد.", status_code=422
            )
    return {
        "goal_type": item.goal_type,
        "target_value": item.target_value,
        "subject_id": item.subject_id,
        "book_id": item.book_id,
        "node_id": item.node_id,
    }


class _WeekData:
    """Week-scoped finals + contexts, built once per call."""

    def __init__(self, db: Session, user_id: int, week_start: date, tz: str):
        start_utc, end_utc = week_window_utc(week_start, tz)
        self.week_sessions = {
            s.id for s in analytics_repo.finished_sessions(db, user_id)
            if start_utc <= s.started_at < end_utc
        }
        pairs = pair_buckets(db, user_id)
        self.week_pairs = {k: v for k, v in pairs.items() if k[0] in self.week_sessions}
        self.week_qids = {qid for (_sid, qid) in self.week_pairs}
        self.ever_qids = {qid for (_sid, qid) in pairs}
        self._db = db
        self._user_id = user_id
        self._ctx: dict[int, BookContext] = {}
        self._active: dict[int, bool] | None = None

    def ctx(self, book_id: int) -> BookContext:
        if book_id not in self._ctx:
            self._ctx[book_id] = build_book_context(
                self._db, user_id=self._user_id, book_id=book_id
            )
        return self._ctx[book_id]

    def book_active(self, book_id: int) -> bool:
        if self._active is None:
            self._active = {}
            for b in book_repo.list_books(self._db):
                a = book_repo.get_activation(self._db, self._user_id, b.id)
                self._active[b.id] = bool(a and a.active)
        return self._active.get(book_id, False)

    def scope_pool(self, *, subject_id: int | None, book_id: int | None, node_id: int | None) -> set[int]:
        if node_id:
            node = book_repo.get_node(self._db, node_id)
            assert node is not None
            return set(self.ctx(node.book_id).pool.get(node_id, set()))
        books = book_repo.list_books(self._db)
        if book_id:
            books = [b for b in books if b.id == book_id]
        if subject_id:
            books = [b for b in books if b.subject_id == subject_id]
        out: set[int] = set()
        for b in books:
            for qids in self.ctx(b.id).pool.values():
                out |= qids
        return out


def _item_title(db: Session, *, subject_id, book_id, node_id) -> str:
    if node_id:
        node = book_repo.get_node(db, node_id)
        return node.title if node else f"گره {node_id}"
    if book_id:
        book = book_repo.get_book(db, book_id)
        return book.title if book else f"کتاب {book_id}"
    if subject_id:
        subject = book_repo.get_subject(db, subject_id)
        return subject.name if subject else f"درس {subject_id}"
    return "همه"


def _progress_item(
    db: Session, data: _WeekData, *, goal_type: str, target: float,
    subject_id: int | None, book_id: int | None, node_id: int | None,
) -> ItemProgressOut:
    pool = data.scope_pool(subject_id=subject_id, book_id=book_id, node_id=node_id)
    week_in_scope = [qid for (_sid, qid) in data.week_pairs if qid in pool]
    attempted = len(set(week_in_scope) & pool)
    coverage = calc_coverage(attempted, len(pool))
    if goal_type == "topic":
        need = 0
        if coverage is None:
            need = 0  # empty pool: nothing to cover
        elif coverage < target:
            need = math.ceil((target - coverage) * len(pool))
        return ItemProgressOut(
            volume=len(week_in_scope), attempted=attempted, pool_total=len(pool),
            coverage=coverage, target=target, remaining=float(need),
            done=(coverage is not None and coverage >= target),
        )
    target_n = int(target)
    return ItemProgressOut(
        volume=len(week_in_scope), attempted=attempted, pool_total=len(pool),
        coverage=coverage, target=target, remaining=float(max(0, target_n - len(week_in_scope))),
        done=len(week_in_scope) >= target_n,
    )


def _goal_out(db: Session, data: _WeekData, goal: WeeklyGoal) -> WeekGoalOut:
    items = [
        GoalItemOut(
            id=it.id, goal_type=it.goal_type,  # type: ignore[arg-type]
            target_value=it.target_value, subject_id=it.subject_id,
            book_id=it.book_id, node_id=it.node_id,
            title=_item_title(
                db, subject_id=it.subject_id, book_id=it.book_id, node_id=it.node_id),
            progress=_progress_item(
                db, data, goal_type=it.goal_type, target=it.target_value,
                subject_id=it.subject_id, book_id=it.book_id, node_id=it.node_id),
        )
        for it in goal.items
    ]
    return WeekGoalOut(
        id=goal.id, week_start=goal.week_start, week_end=goal.week_end,
        active=goal.active, items=items,
        sessions_in_week=len(data.week_sessions),
        week_volume_unique=len(data.week_pairs),
        week_attempted_unique=len(data.week_qids),
    )


def create_week_goal(db: Session, *, user_id: int, week: str, payload: WeekGoalCreate) -> WeekGoalOut:
    user = get_or_create_single_user(db, user_id)
    start, end = parse_week(week)
    if repo.get_goal_by_week(db, user.id, start):
        raise AppError("goal_exists", "برای این هفته هدف ثبت شده است.", status_code=409)
    validated = [_validate_item(db, it) for it in payload.items]
    try:
        goal = repo.create_goal(db, user_id=user.id, week_start=start, week_end=end, active=payload.active)
        for it in validated:
            repo.add_item(db, goal_id=goal.id, **it)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(goal)
    return _goal_out(db, _WeekData(db, user.id, start, user.timezone), goal)


def get_week_goal(db: Session, *, user_id: int, week: str) -> WeekGoalOut:
    user = get_or_create_single_user(db, user_id)
    start, _end = parse_week(week)
    goal = repo.get_goal_by_week(db, user.id, start)
    if goal is None:
        raise AppError("goal_not_found", "برای این هفته هدفی ثبت نشده است.",
                       status_code=404, details={"week_start": str(start)})
    return _goal_out(db, _WeekData(db, user.id, start, user.timezone), goal)


def update_goal(db: Session, *, user_id: int, goal_id: int, payload: WeekGoalPatch) -> WeekGoalOut:
    user = get_or_create_single_user(db, user_id)
    goal = repo.get_goal(db, user.id, goal_id)
    if goal is None:
        raise AppError("goal_not_found", "هدف یافت نشد.", status_code=404)
    validated = [_validate_item(db, it) for it in payload.items] if payload.items else None
    try:
        if validated is not None:
            repo.replace_items(db, goal, validated)
        if payload.active is not None:
            goal.active = payload.active
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(goal)
    return _goal_out(db, _WeekData(db, user.id, goal.week_start, user.timezone), goal)


def _suggested_parity(last: str | None) -> str:
    return {"odd": "even", "even": "odd"}.get(last or "", "any")


def candidate_tasks(
    db: Session, *, user_id: int, goal_id: int, limit: int
) -> CandidateTasksOut:
    user = get_or_create_single_user(db, user_id)
    if not 1 <= limit <= 100:
        raise AppError("invalid_limit", "limit باید بین ۱ تا ۱۰۰ باشد.", status_code=422)
    goal = repo.get_goal(db, user.id, goal_id)
    if goal is None:
        raise AppError("goal_not_found", "هدف یافت نشد.", status_code=404)
    from app.services import student_state

    data = _WeekData(db, user.id, goal.week_start, user.timezone)
    signals = student_state.get_signals(db, user_id=user.id)
    weak = signals.weak_scores
    ranked_weak_nodes = signals.ranked_weak_nodes

    acc: dict[int, dict] = defaultdict(lambda: {
        "sources": set(), "item_ids": set(), "test": False, "review": False,
        "suggested": 0, "review_total": 0, "review_high": 0,
    })
    in_scope: set[int] = set()  # nodes touched by goal items (for review filtering)

    def touch_scope_node(nid: int) -> None:
        in_scope.add(nid)

    for it in goal.items:
        progress = _progress_item(
            db, data, goal_type=it.goal_type, target=it.target_value,
            subject_id=it.subject_id, book_id=it.book_id, node_id=it.node_id)
        if it.goal_type == "topic":
            assert it.node_id is not None
            node = book_repo.get_node(db, it.node_id)
            assert node is not None
            touch_scope_node(it.node_id)
            if not data.book_active(node.book_id):
                continue  # inactive books: progress yes, candidates no
            if progress.done:
                continue
            entry = acc[it.node_id]
            entry["sources"].add("goal_topic")
            entry["item_ids"].add(it.id)
            entry["test"] = True
            entry["suggested"] = max(entry["suggested"], int(progress.remaining))
        else:
            if progress.done:
                continue
            remaining = int(progress.remaining)
            nodes = _count_scope_nodes(db, data, subject_id=it.subject_id,
                                       book_id=it.book_id, node_id=it.node_id)
            for nid in nodes:
                touch_scope_node(nid)
            picks = _pick_count_nodes(db, data, weak, nodes, k=2)
            for nid in picks:
                node = book_repo.get_node(db, nid)
                assert node is not None
                if not data.book_active(node.book_id):
                    continue
                pool = data.ctx(node.book_id).pool.get(nid, set())
                remaining_ever = len(pool - data.ever_qids)
                entry = acc[nid]
                entry["sources"].add("goal_count")
                entry["item_ids"].add(it.id)
                entry["test"] = True
                entry["suggested"] = max(
                    entry["suggested"], min(remaining, remaining_ever or len(pool) or 1))

    # Standalone weakness candidates (top 3 uncovered, must have fresh pool).
    for nid in ranked_weak_nodes[:3]:
        if nid in acc:
            continue
        node = book_repo.get_node(db, nid)
        if node is None or not data.book_active(node.book_id):
            continue
        pool = data.ctx(node.book_id).pool.get(nid, set())
        remaining_ever = len(pool - data.ever_qids)
        if not pool or remaining_ever == 0:
            continue  # exhausted pools surface via review, not new tests
        entry = acc[nid]
        entry["sources"].add("weakness")
        entry["test"] = True
        entry["suggested"] = remaining_ever

    # Review candidates: pending questions grouped by node, in goal scope.
    review_groups = signals.review_by_node
    scoped = {nid: g for nid, g in review_groups.items() if nid in in_scope} or review_groups
    top_review = sorted(scoped.items(), key=lambda kv: (-kv[1]["high"], -kv[1]["total"]))[:3]
    for nid, g in top_review:
        node = book_repo.get_node(db, nid)
        if node is None or not data.book_active(node.book_id):
            continue
        entry = acc[nid]
        entry["sources"].add("review")
        entry["review"] = True
        entry["review_total"] = g["total"]
        entry["review_high"] = g["high"]
        if not entry["test"]:
            entry["suggested"] = g["total"]

    items: list[CandidateTaskOut] = []
    for nid, entry in acc.items():
        node = book_repo.get_node(db, nid)
        assert node is not None
        ctx = data.ctx(node.book_id)
        pool = ctx.pool.get(nid, set())
        score = weak.get(nid, 0.0)
        remaining_ever = len(pool - data.ever_qids)
        remaining_week = len(pool - data.week_qids)
        volume_week = sum(1 for (_sid, qid) in data.week_pairs if qid in pool)
        base = max(SOURCE_BASE_SCORE[s] for s in entry["sources"])
        priority = min(1.0, base + min(score * 0.25, 0.25)
                       + (len(pool - data.ever_qids) / len(pool) * 0.15 if pool else 0.0))
        last_parity = ctx.parity.get(nid)
        suggested_parity = _suggested_parity(last_parity)
        parts: list[str] = []
        if "goal_topic" in entry["sources"]:
            parts.append(f"هدف موضوعی هفته ({node.title})")
        if "goal_count" in entry["sources"]:
            parts.append("هدف تعداد هفته")
        if score > 0:
            parts.append(f"ضعف اخیر (نمره {round(score * 100)}٪)")
        if "review" in entry["sources"]:
            rp = f"{entry['review_total']} مرور باز"
            if entry["review_high"]:
                rp += f" ({entry['review_high']} بحرانی)"
            parts.append(rp)
        if last_parity in ("odd", "even"):
            parts.append(f"مخالف دفعه قبل ({PARITY_FA[suggested_parity]})")
        else:
            parts.append("شروع آزاد (بدون سابقه زوج/فرد)")
        items.append(CandidateTaskOut(
            kind="test" if entry["test"] else "review",
            sources=sorted(entry["sources"]),
            source_item_ids=sorted(entry["item_ids"]),
            node_id=nid, book_id=node.book_id,
            title=node.title, path=ctx.path.get(nid, node.title),
            suggested_count=max(entry["suggested"], 1),
            suggested_parity=suggested_parity,  # type: ignore[arg-type]
            priority_score=round(priority, 3),
            recommendation_reason=" + ".join(parts),
            pool_total=len(pool),
            remaining_never=remaining_ever,
            remaining_week=remaining_week,
            volume_week=volume_week,
            weakness_score=round(score, 3),
        ))
    items.sort(key=lambda c: (-c.priority_score, -c.remaining_never, c.node_id))
    return CandidateTasksOut(goal_id=goal.id, items=items[:limit])


def _count_scope_nodes(
    db: Session, data: _WeekData, *, subject_id: int | None,
    book_id: int | None, node_id: int | None,
) -> list[int]:
    """Nodes a count item may suggest work on (active books only)."""
    books = book_repo.list_books(db)
    if node_id:
        node = book_repo.get_node(db, node_id)
        assert node is not None
        books = [b for b in books if b.id == node.book_id]
    if book_id:
        books = [b for b in books if b.id == book_id]
    if subject_id:
        books = [b for b in books if b.subject_id == subject_id]
    out: list[int] = []
    for b in books:
        if not data.book_active(b.id):
            continue
        ctx = data.ctx(b.id)
        if node_id:
            # The node itself plus descendants.
            stack = [node_id]
            while stack:
                cur = stack.pop()
                out.append(cur)
                stack.extend(n.id for n in ctx.children.get(cur, []))
        else:
            out.extend(n.id for n in ctx.nodes)
    return out


def _pick_count_nodes(
    db: Session, data: _WeekData, weak: dict[int, float], nodes: list[int], *, k: int
) -> list[int]:
    scored: list[tuple[float, float, int, int]] = []
    for nid in nodes:
        node = book_repo.get_node(db, nid)
        if node is None:
            continue
        pool = data.ctx(node.book_id).pool.get(nid, set())
        if not pool:
            continue
        cov = len(pool & data.week_qids) / len(pool)
        scored.append((-weak.get(nid, 0.0), cov, -len(pool - data.ever_qids), nid))
    scored.sort()
    return [nid for _, _, _, nid in scored[:k]]



