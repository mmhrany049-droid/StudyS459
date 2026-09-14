"""Config-driven book importer (spec 05).

Generic for ANY book: no per-book conditions (spec 03 forbids them).
Flow: validate (pure domain) -> dedupe by content hash -> insert atomically.

- Same stable_key + same hash  -> idempotent success ("unchanged").
- Same stable_key + other hash -> 409 (re-import with changes is deferred;
  silently merging structural changes over history would be unsafe).
"""

from sqlalchemy.orm import Session

from app.domain.book_config import BookConfigError, validate_book_config
from app.errors import AppError
from app.logging_config import get_logger
from app.models import BookNode, Question, QuestionTopicMap, TestSet
from app.repositories import books as repo
from app.schemas.books import ImportOut
from app.services.users import get_or_create_single_user

logger = get_logger(__name__)


def _counts(db: Session, book_id: int) -> tuple[int, int, int]:
    return (
        repo.count_nodes(db, book_id),
        repo.count_test_sets(db, book_id),
        repo.count_questions(db, book_id),
    )


def import_book_config(db: Session, *, user_id: int, config: dict) -> ImportOut:
    try:
        validated = validate_book_config(config)
    except BookConfigError as exc:
        details: dict = {
            "issues": [{"path": i.path, "message": i.message} for i in exc.issues],
            "truncated": exc.truncated,
        }
        raise AppError(
            "invalid_book_config",
            f"Book config is invalid ({len(exc.issues)} issue(s))",
            status_code=422,
            details=details,
        ) from exc

    user = get_or_create_single_user(db, user_id)
    existing = repo.get_book_by_stable_key(db, validated.book.stable_key)
    if existing is not None:
        latest = repo.get_latest_import(db, existing.id)
        if latest is not None and latest.config_hash == validated.content_hash:
            nodes, sets, questions = _counts(db, existing.id)
            logger.info("import skipped (unchanged): book=%s", existing.stable_key)
            return ImportOut(
                status="unchanged",
                book_id=existing.id,
                stable_key=existing.stable_key,
                node_count=nodes,
                test_set_count=sets,
                question_count=questions,
            )
        raise AppError(
            "book_already_imported",
            "This book was already imported with different content. "
            "Re-import with changes is not supported in v1 (history-safe).",
            status_code=409,
            details={"book_id": existing.id, "stable_key": existing.stable_key},
        )

    try:
        subject = repo.get_or_create_subject(
            db,
            name=validated.book.subject.name,
            grade=validated.book.subject.grade,
            track=validated.book.subject.track,
            type=validated.book.subject.type,
        )
        book = repo.create_book(
            db,
            stable_key=validated.book.stable_key,
            title=validated.book.title,
            publisher=validated.book.publisher,
            subject_id=subject.id,
            grade=validated.book.grade,
            track=validated.book.track,
            edition=validated.book.edition,
            config_version=validated.book.config_version,
        )

        node_ids: dict[str, int] = {}
        pending_nodes = [
            BookNode(
                book_id=book.id,
                parent_id=None,  # wired after flush (keys -> ids)
                node_type=n.type,
                title=n.title,
                code=n.code,
                order_index=n.order,
                meta=n.meta,
            )
            for n in validated.nodes
        ]
        db.add_all(pending_nodes)
        db.flush()
        for node_cfg, node_row in zip(validated.nodes, pending_nodes, strict=True):
            node_ids[node_cfg.key] = node_row.id
        for node_cfg, node_row in zip(validated.nodes, pending_nodes, strict=True):
            if node_cfg.parent_key is not None:
                node_row.parent_id = node_ids[node_cfg.parent_key]
        db.flush()

        test_set_ids: dict[str, int] = {}
        pending_sets = [
            TestSet(
                book_id=book.id,
                title=t.title,
                test_type=t.test_type,
                node_id=node_ids[t.node_key] if t.node_key else None,
                meta=t.meta,
            )
            for t in validated.test_sets
        ]
        db.add_all(pending_sets)
        db.flush()
        for ts_cfg, ts_row in zip(validated.test_sets, pending_sets, strict=True):
            test_set_ids[ts_cfg.key] = ts_row.id

        pending_questions = [
            Question(
                book_id=book.id,
                stable_key=q.stable_key,
                test_set_id=test_set_ids[q.test_set_key],
                sequence_no=q.sequence_no,
                difficulty_level=q.difficulty,
                answer_type=q.answer_type,
                answer_key=q.answer_key,
                meta=q.meta,
            )
            for q in validated.questions
        ]
        db.add_all(pending_questions)
        db.flush()
        db.add_all(
            QuestionTopicMap(question_id=q_row.id, node_id=node_ids[topic])
            for q_cfg, q_row in zip(validated.questions, pending_questions, strict=True)
            for topic in q_cfg.topic_keys
        )

        repo.record_import(
            db,
            book_id=book.id,
            config_hash=validated.content_hash,
            config_version=validated.book.config_version,
        )
        # Freshly imported books start active (single-user MVP); the user
        # can deactivate anytime without losing history.
        repo.set_activation(db, user.id, book.id, active=True)
        db.commit()
    except Exception:
        db.rollback()
        raise

    nodes, sets, questions = _counts(db, book.id)
    logger.info(
        "imported book=%s nodes=%d sets=%d questions=%d",
        book.stable_key, nodes, sets, questions,
    )
    return ImportOut(
        status="imported",
        book_id=book.id,
        stable_key=book.stable_key,
        node_count=nodes,
        test_set_count=sets,
        question_count=questions,
    )
