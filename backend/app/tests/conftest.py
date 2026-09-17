"""Shared pytest fixtures: every test gets a fresh SQLite file + seeded content."""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db import models  # noqa: E402
from app.db import base as db_base  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    os.environ["STUDYS459_DB_PATH"] = str(tmp_path / "test.db")
    db_base.reset_engine()
    db_base.init_db()
    session = db_base.get_session_factory()()
    try:
        yield session
    finally:
        session.close()
        db_base.reset_engine()


@pytest.fixture()
def user(db):
    from app.services import common

    row = common.create_user(db, "دانش‌آموز تست", "tester")
    db.commit()
    return row


@pytest.fixture()
def seeded(db, user):
    from app.db.seed import seed_all

    result = seed_all(db, user)
    db.commit()
    return result


@pytest.fixture()
def client(tmp_path):
    os.environ["STUDYS459_DB_PATH"] = str(tmp_path / "api.db")
    os.environ["STUDYS459_AUTOSEED"] = "1"
    db_base.reset_engine()
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    db_base.reset_engine()


@pytest.fixture()
def book_with_questions(db, user, seeded):
    """A ready topic with 20 questions and answer keys."""
    from app.services import common, questions

    topic = db.query(models.Topic).filter(models.Topic.is_leaf.is_(True)).first()
    book = db.get(models.Book, topic.book_id)
    questions.add_question_range(db, user, book_id=book.id, topic_id=topic.id, seq_from=1, seq_to=20, level=2)
    questions.set_answer_keys_bulk(
        db,
        user,
        book_id=book.id,
        topic_id=topic.id,
        items=[{"sequence_no": i, "answer_key": str((i % 4) + 1)} for i in range(1, 21)],
    )
    db.commit()
    return {"book": book, "topic": topic}
