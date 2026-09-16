"""الگوریتم مرور V2 — خوشه موضوعی نزدیک + ترتیب تصادفی.

اعداد قطعی (06_REVIEW_ALGORITHM_V2 و 14_NUMERIC):
- حداکثر ۲۵ سوال در جلسه مرور
- حداقل مطلوب خوشه: ۸
- Critical: wrong_count ≥ ۲ → بازگشت حداکثر ۲ روز
- wrong/unanswered عادی → حداکثر ۳ روز
- پاسخ درست → resolve؛ غلط مجدد → priority بالا و scheduled_for زودتر
- parity و range در مرور اعمال نمی‌شود
- پنج‌شنبه/جمعه وزن مرور بالاتر
"""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.config as cfg
from app.jalali import today_tehran
from app.models import BookNode, Question, QuestionTopicMap, ReviewQueueItem


def _node_ancestors(db: Session, node_id: int, depth: int) -> set[int]:
    """والدها تا عمق مشخص."""
    result = set()
    current = node_id
    for _ in range(depth):
        row = db.execute(select(BookNode.parent_id).where(BookNode.id == current)).scalar_one_or_none()
        if row is None:
            break
        result.add(row)
        current = row
    return result


def _question_nodes(db: Session, question_ids: list[int]) -> dict[int, set[int]]:
    if not question_ids:
        return {}
    rows = db.execute(
        select(QuestionTopicMap.question_id, QuestionTopicMap.node_id)
        .where(QuestionTopicMap.question_id.in_(question_ids))
    ).all()
    m: dict[int, set[int]] = {q: set() for q in question_ids}
    for qid, nid in rows:
        m[qid].add(nid)
    return m


def _ancestry_cache(db: Session, node_ids: set[int]) -> dict[int, set[int]]:
    """node_id → {خود + والد + پدربزرگ} برای تعریف «نزدیک»."""
    cache: dict[int, set[int]] = {}
    for nid in node_ids:
        if nid in cache:
            continue
        s = {nid} | _node_ancestors(db, nid, 2)
        cache[nid] = s
    return cache


def are_close(db: Session, nodes_a: set[int], nodes_b: set[int],
              ancestry: dict[int, set[int]]) -> bool:
    """دو سوال نزدیک‌اند اگر node مشترک داشته باشند یا والد مشترک تا عمق ۲."""
    for a in nodes_a:
        for b in nodes_b:
            if a == b:
                return True
            if ancestry.get(a, {a}) & ancestry.get(b, {b}):
                return True
    return False


def build_review_session(db: Session, user_id: int, count: int | None = None) -> list[Question]:
    """ساخت جلسه مرور: انتخاب کاندید → خوشه → پر کردن → shuffle.

    آیتم‌ها بلافاصله بعد از غلط/نزده قابل مرورند؛ scheduled_for «مهلت بازگشت» است
    (critical حداکثر ۲ روز، عادی حداکثر ۳ روز) و اولویت را تعیین می‌کند.
    """
    today = today_tehran()
    limit = count or cfg.REVIEW_MAX_QUESTIONS_PER_SESSION
    limit = min(limit, cfg.REVIEW_MAX_QUESTIONS_PER_SESSION)

    items = list(db.scalars(
        select(ReviewQueueItem).where(
            ReviewQueueItem.user_id == user_id,
            ReviewQueueItem.status == "pending",
        )
    ))

    def sort_key(it: ReviewQueueItem):
        is_critical = it.wrong_count >= cfg.REVIEW_CRITICAL_WRONG_COUNT
        overdue = it.scheduled_for < today  # از مهلت گذشته → فوری‌ترین
        reason_rank = 0 if it.reason == "wrong" else (1 if it.reason == "unanswered" else 2)
        return (0 if overdue else 1, 0 if is_critical else 1, reason_rank,
                it.scheduled_for, -it.priority, it.id)

    items.sort(key=sort_key)
    candidates = items[:limit]
    if not candidates:
        return []

    qids = [it.entity_id for it in candidates]
    questions = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(qids)))}
    qnodes = _question_nodes(db, qids)
    all_nodes = set().union(*qnodes.values()) if qnodes else set()
    ancestry = _ancestry_cache(db, all_nodes)

    # ساخت خوشه موضوعی: از قوی‌ترین کاندید شروع و نزدیک‌ها را اضافه کن
    cluster: list[int] = []
    seed_id = qids[0]
    cluster.append(seed_id)
    for qid in qids[1:]:
        if len(cluster) >= limit:
            break
        if are_close(db, qnodes[qid], qnodes[seed_id] | set().union(*[qnodes[c] for c in cluster]),
                     ancestry):
            cluster.append(qid)

    # اگر خوشه کمتر از حداقل مطلوب بود، از نزدیک‌ترین nodeهای مجاور پر کن
    if len(cluster) < cfg.REVIEW_MIN_CLUSTER_SIZE:
        seed_nodes = qnodes[seed_id]
        remaining = [q for q in qids if q not in cluster]
        # نزدیک به هر عضو خوشه (نه فقط seed)
        cluster_nodes = set().union(*[qnodes[c] for c in cluster]) if cluster else seed_nodes
        for qid in remaining:
            if len(cluster) >= cfg.REVIEW_MIN_CLUSTER_SIZE:
                break
            if are_close(db, qnodes[qid], cluster_nodes, ancestry):
                cluster.append(qid)
        # هنوز کم است → از صف کل به ترتیب اولویت پر کن (تا حداقل خوشه یا limit)
        for qid in remaining:
            if len(cluster) >= min(cfg.REVIEW_MIN_CLUSTER_SIZE, limit):
                break
            if qid not in cluster:
                cluster.append(qid)

    # ترتیب نهایی نمایش: shuffle تصادفی (نه به ترتیب sequence)
    random.shuffle(cluster)
    return [questions[qid] for qid in cluster if qid in questions]


def enqueue_review(db: Session, user_id: int, question_id: int, result: str) -> None:
    """wrong/unanswered → صف مرور؛ درست در مرور → resolve."""
    today = today_tehran()
    item = db.execute(
        select(ReviewQueueItem).where(
            ReviewQueueItem.user_id == user_id,
            ReviewQueueItem.entity_id == question_id,
            ReviewQueueItem.status == "pending",
        )
    ).scalar_one_or_none()

    if result in ("wrong", "unanswered"):
        if item is None:
            item = ReviewQueueItem(
                user_id=user_id, entity_id=question_id, reason=result,
                wrong_count=1 if result == "wrong" else 0,
                priority=1 if result == "wrong" else 0,
                scheduled_for=today + timedelta(days=cfg.REVIEW_NORMAL_MAX_DAYS),
                last_result=result,
            )
            db.add(item)
        else:
            item.last_result = result
            if result == "wrong":
                item.wrong_count += 1
                item.priority += 1
                # غلط مجدد → زودتر شدن scheduled_for (critical: ۲ روز، عادی: ۳ روز)
                max_days = (cfg.REVIEW_CRITICAL_MAX_DAYS
                            if item.wrong_count >= cfg.REVIEW_CRITICAL_WRONG_COUNT
                            else cfg.REVIEW_NORMAL_MAX_DAYS)
                item.scheduled_for = min(item.scheduled_for,
                                         today + timedelta(days=max_days))
    elif result == "correct":
        if item is not None:
            # پاسخ درست در مرور → خروج از صف
            item.status = "resolved"
            item.last_result = "correct"


def pending_review_count(db: Session, user_id: int) -> int:
    today = today_tehran()
    return len(list(db.scalars(
        select(ReviewQueueItem.id).where(
            ReviewQueueItem.user_id == user_id,
            ReviewQueueItem.status == "pending",
            ReviewQueueItem.scheduled_for <= today,
        ))))
