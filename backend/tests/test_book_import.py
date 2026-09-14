"""Integration tests: importer service + read services (temp DB)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Book, Question, QuestionTopicMap, Subject, User
from app.services import books as book_service
from app.services.book_importer import import_book_config
from tests.helpers import base_config


def test_import_creates_everything(db_session: Session) -> None:
    result = import_book_config(db_session, user_id=1, config=base_config())
    assert result.status == "imported"
    assert (result.node_count, result.test_set_count, result.question_count) == (3, 2, 3)

    assert db_session.execute(select(func.count()).select_from(Subject)).scalar() == 1
    assert db_session.execute(select(func.count()).select_from(Book)).scalar() == 1
    assert db_session.execute(select(func.count()).select_from(Question)).scalar() == 3
    # 1 default topic + 1 default topic + 2 explicit topics
    assert db_session.execute(select(func.count()).select_from(QuestionTopicMap)).scalar() == 4

    detail = book_service.get_book_detail(db_session, user_id=1, book_id=result.book_id)
    assert detail.active is True  # auto-activated on import
    assert detail.activated_at is not None
    assert detail.subject.name == "شیمی"


def test_reimport_identical_is_noop(db_session: Session) -> None:
    first = import_book_config(db_session, user_id=1, config=base_config())
    second = import_book_config(db_session, user_id=1, config=base_config())
    assert second.status == "unchanged"
    assert second.book_id == first.book_id
    assert db_session.execute(select(func.count()).select_from(Question)).scalar() == 3


def test_reimport_changed_is_conflict(db_session: Session) -> None:
    import_book_config(db_session, user_id=1, config=base_config())
    changed = base_config()
    changed["book"]["title"] = "تغییر"
    with pytest.raises(AppError) as e:
        import_book_config(db_session, user_id=1, config=changed)
    assert e.value.code == "book_already_imported"
    assert e.value.status_code == 409
    assert db_session.execute(select(func.count()).select_from(Book)).scalar() == 1


def test_import_invalid_raises_422_with_issues(db_session: Session) -> None:
    with pytest.raises(AppError) as e:
        import_book_config(db_session, user_id=1, config={"book": {}})
    assert e.value.code == "invalid_book_config"
    assert e.value.status_code == 422
    assert len(e.value.details["issues"]) > 0
    assert db_session.execute(select(func.count()).select_from(Book)).scalar() == 0


def test_import_recreates_missing_user(db_session: Session) -> None:
    db_session.delete(db_session.get(User, 1))
    db_session.commit()
    import_book_config(db_session, user_id=1, config=base_config())
    assert db_session.get(User, 1) is not None


def test_tree_shape_and_leaves(db_session: Session) -> None:
    result = import_book_config(db_session, user_id=1, config=base_config())
    tree = book_service.get_book_tree(db_session, book_id=result.book_id)
    assert len(tree.nodes) == 1
    ch1 = tree.nodes[0]
    assert ch1.is_leaf is False
    assert [c.title for c in ch1.children] == ["عنوان ۱", "عنوان ۲"]
    assert all(c.is_leaf for c in ch1.children)
    t1 = ch1.children[0]
    assert len(t1.test_sets) == 1
    assert t1.test_sets[0].title == "تمرین ۱"
    assert t1.test_sets[0].question_count == 2


def test_children_service(db_session: Session) -> None:
    result = import_book_config(db_session, user_id=1, config=base_config())
    tree = book_service.get_book_tree(db_session, book_id=result.book_id)
    ch1_id = tree.nodes[0].id
    out = book_service.get_node_children(db_session, node_id=ch1_id)
    assert out.node_id == ch1_id
    assert [c.order_index for c in out.children] == [1, 2]
    leaf_id = out.children[0].id
    assert book_service.get_node_children(db_session, node_id=leaf_id).children == []


def test_activation_roundtrip_keeps_row(db_session: Session) -> None:
    result = import_book_config(db_session, user_id=1, config=base_config())
    off = book_service.set_book_active(db_session, user_id=1, book_id=result.book_id, active=False)
    assert off.active is False
    detail = book_service.get_book_detail(db_session, user_id=1, book_id=result.book_id)
    assert detail.active is False
    # Book + questions untouched (history-safe).
    assert detail.question_count == 3
    on = book_service.set_book_active(db_session, user_id=1, book_id=result.book_id, active=True)
    assert on.active is True
