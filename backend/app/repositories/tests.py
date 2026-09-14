"""Test Engine persistence queries (spec 04 test tables)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import (
    BookNode,
    NodeParityState,
    Question,
    QuestionAttempt,
    QuestionTopicMap,
    TestSession,
    TestSessionQuestion,
    TestSet,
)


# -- sessions ----------------------------------------------------------
def get_session(db: Session, session_id: int) -> TestSession | None:
    return db.get(TestSession, session_id)


def create_session(
    db: Session,
    *,
    user_id: int,
    task_id: int | None,
    timed: bool,
    time_limit_seconds: int | None,
    sequence_from: int | None,
    sequence_to: int | None,
    parity: str,
) -> TestSession:
    session = TestSession(
        user_id=user_id,
        task_id=task_id,
        timed=timed,
        time_limit_seconds=time_limit_seconds,
        sequence_from=sequence_from,
        sequence_to=sequence_to,
        parity=parity,
        status="in_progress",
    )
    db.add(session)
    db.flush()
    return session


def add_session_questions(db: Session, *, session_id: int, question_ids: list[int]) -> None:
    db.add_all(
        TestSessionQuestion(session_id=session_id, question_id=qid, display_order=i + 1)
        for i, qid in enumerate(question_ids)
    )
    db.flush()


def get_session_question_ids(db: Session, session_id: int) -> list[int]:
    stmt = (
        select(TestSessionQuestion.question_id)
        .where(TestSessionQuestion.session_id == session_id)
        .order_by(TestSessionQuestion.display_order)
    )
    return list(db.execute(stmt).scalars().all())


def get_session_questions_detail(db: Session, session_id: int) -> list[tuple]:
    """Ordered (session_question, question, test_set_title) rows."""
    stmt = (
        select(TestSessionQuestion, Question, TestSet.title)
        .join(Question, Question.id == TestSessionQuestion.question_id)
        .join(TestSet, TestSet.id == Question.test_set_id)
        .where(TestSessionQuestion.session_id == session_id)
        .order_by(TestSessionQuestion.display_order)
    )
    return list(db.execute(stmt).all())


# -- pool --------------------------------------------------------------
def node_subtree_ids(db: Session, node_id: int) -> list[int]:
    """node_id + all descendant ids (pool = node + descendants)."""
    rows = db.execute(select(BookNode.id, BookNode.parent_id)).all()
    children: dict[int | None, list[int]] = {}
    for nid, parent in rows:
        children.setdefault(parent, []).append(nid)
    out, stack = [], [node_id]
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(children.get(current, []))
    return out


def pool_questions(
    db: Session,
    *,
    book_id: int,
    node_ids: list[int],
    sequence_from: int | None,
    sequence_to: int | None,
) -> list[tuple[int, int]]:
    """Distinct (question_id, sequence_no) mapped to any of node_ids, in range."""
    stmt = (
        select(Question.id, Question.sequence_no)
        .distinct()
        .join(QuestionTopicMap, QuestionTopicMap.question_id == Question.id)
        .where(Question.book_id == book_id, QuestionTopicMap.node_id.in_(node_ids))
    )
    if sequence_from is not None:
        stmt = stmt.where(Question.sequence_no >= sequence_from)
    if sequence_to is not None:
        stmt = stmt.where(Question.sequence_no <= sequence_to)
    return [(qid, seq) for qid, seq in db.execute(stmt).all()]


def topics_for_questions(db: Session, question_ids: list[int]) -> dict[int, list[tuple[int, str]]]:
    if not question_ids:
        return {}
    stmt = (
        select(QuestionTopicMap.question_id, BookNode.id, BookNode.title)
        .join(BookNode, BookNode.id == QuestionTopicMap.node_id)
        .where(QuestionTopicMap.question_id.in_(question_ids))
    )
    out: dict[int, list[tuple[int, str]]] = {qid: [] for qid in question_ids}
    for qid, nid, title in db.execute(stmt).all():
        out[qid].append((nid, title))
    return out


# -- attempts ----------------------------------------------------------
def get_attempt_by_client_id(db: Session, client_attempt_id: str) -> QuestionAttempt | None:
    stmt = select(QuestionAttempt).where(QuestionAttempt.client_attempt_id == client_attempt_id)
    return db.execute(stmt).scalar_one_or_none()


def create_attempt(
    db: Session,
    *,
    session_id: int,
    question_id: int,
    user_id: int,
    answer: str | None,
    response_time_seconds: int | None,
    client_attempt_id: str,
) -> QuestionAttempt:
    attempt = QuestionAttempt(
        session_id=session_id,
        question_id=question_id,
        user_id=user_id,
        answer=answer,
        result=None,  # correction happens at finish (spec 06 lifecycle)
        response_time_seconds=response_time_seconds,
        client_attempt_id=client_attempt_id,
    )
    db.add(attempt)
    db.flush()
    return attempt


def latest_attempts_by_question(db: Session, session_id: int) -> dict[int, QuestionAttempt]:
    """Latest row per question (max id wins — ids are monotonic)."""
    sub = (
        select(
            QuestionAttempt.question_id,
            func.max(QuestionAttempt.id).label("max_id"),
        )
        .where(QuestionAttempt.session_id == session_id)
        .group_by(QuestionAttempt.question_id)
        .subquery()
    )
    stmt = select(QuestionAttempt).join(sub, QuestionAttempt.id == sub.c.max_id)
    return {a.question_id: a for a in db.execute(stmt).scalars().all()}


def count_attempts(db: Session, session_id: int) -> int:
    stmt = select(func.count(QuestionAttempt.id)).where(QuestionAttempt.session_id == session_id)
    return int(db.execute(stmt).scalar() or 0)


# -- parity ------------------------------------------------------------
def get_parity_state(db: Session, user_id: int, node_id: int) -> NodeParityState | None:
    stmt = select(NodeParityState).where(
        NodeParityState.user_id == user_id, NodeParityState.node_id == node_id
    )
    return db.execute(stmt).scalar_one_or_none()


def update_parity_state(db: Session, *, user_id: int, node_id: int, parity: str) -> NodeParityState:
    row = get_parity_state(db, user_id, node_id)
    if row is None:
        row = NodeParityState(user_id=user_id, node_id=node_id, last_parity=parity)
        db.add(row)
    else:
        row.last_parity = parity
        row.last_used_at = utcnow()
    db.flush()
    return row
