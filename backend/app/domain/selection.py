"""موتور انتخاب سوال — هسته V1 (Range + Parity).

قوانین قطعی (06_TEST_ENGINE و 14_NUMERIC_ALGORITHMS_REFERENCE):
1. بازه sequence فقط سوالهای داخل آن را نگه می‌دارد.
2. parity = odd → فقط فرد؛ even → فقط زوج؛ any → همه.
3. انتخاب نهایی از pool مجاز تصادفی و بدون تکرار است.
4. اگر تعداد کافی نباشد: session ساخته نمی‌شود + پیام دقیق
   «فقط X سوال با این شرایط وجود دارد.»
"""

from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BookNode, NodeParityState, Question, TestSet, User


class InsufficientQuestions(Exception):
    """تعداد سوال کافی در pool نیست — پیام دقیق طبق سند."""

    def __init__(self, available: int):
        self.available = available
        super().__init__(f"فقط {available} سوال با این شرایط وجود دارد.")


def build_pool(db: Session, test_set_id: int, sequence_from: int | None, sequence_to: int | None,
               parity: str) -> list[Question]:
    stmt = select(Question).where(Question.test_set_id == test_set_id)
    if sequence_from is not None:
        stmt = stmt.where(Question.sequence_no >= sequence_from)
    if sequence_to is not None:
        stmt = stmt.where(Question.sequence_no <= sequence_to)
    if parity == "odd":
        stmt = stmt.where(Question.sequence_no % 2 == 1)
    elif parity == "even":
        stmt = stmt.where(Question.sequence_no % 2 == 0)
    return list(db.scalars(stmt.order_by(Question.sequence_no)))


def select_questions(db: Session, test_set_id: int, count: int,
                     sequence_from: int | None = None, sequence_to: int | None = None,
                     parity: str = "any") -> list[Question]:
    pool = build_pool(db, test_set_id, sequence_from, sequence_to, parity)
    if len(pool) < count:
        raise InsufficientQuestions(len(pool))
    # تصادفی، بدون تکرار داخل session
    return random.sample(pool, count)


def update_parity_state(db: Session, user_id: int, node_id: int, parity: str) -> None:
    """آخرین parity استفاده‌شده برای node ذخیره می‌شود."""
    if parity not in ("odd", "even"):
        return
    st = db.execute(
        select(NodeParityState).where(NodeParityState.user_id == user_id,
                                      NodeParityState.node_id == node_id)
    ).scalar_one_or_none()
    if st is None:
        st = NodeParityState(user_id=user_id, node_id=node_id, last_parity=parity)
        db.add(st)
    else:
        st.last_parity = parity


def suggest_parity(db: Session, user_id: int, node_id: int) -> str:
    """parity مخالف آخرین استفاده؛ پیش‌فرض odd طبق قانون قطعی V2."""
    st = db.execute(
        select(NodeParityState).where(NodeParityState.user_id == user_id,
                                      NodeParityState.node_id == node_id)
    ).scalar_one_or_none()
    if st is None:
        return "odd"
    return "even" if st.last_parity == "odd" else "odd"


def node_test_sets(db: Session, node_id: int) -> list[TestSet]:
    return list(db.scalars(
        select(TestSet).where(TestSet.node_id == node_id).order_by(TestSet.id)))


def descendant_test_sets(db: Session, node: BookNode) -> list[TestSet]:
    """همهٔ test setهای زیر این node (شامل خودش)."""
    ids = [node.id]
    frontier = [node.id]
    while frontier:
        children = list(db.scalars(
            select(BookNode.id).where(BookNode.parent_id.in_(frontier))))
        ids.extend(children)
        frontier = children
    return list(db.scalars(select(TestSet).where(TestSet.node_id.in_(ids)).order_by(TestSet.id)))
