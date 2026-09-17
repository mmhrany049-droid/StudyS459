"""Database engine / session plumbing.

SQLite by default, PostgreSQL-ready: all models avoid SQLite-only features,
all timestamps are stored as timezone-naive UTC, all money-like values are
integers and all JSON payloads go through :class:`JSONType`.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

DEFAULT_DB_PATH = os.path.join("data", "studys459.db")


class Base(DeclarativeBase):
    pass


class SafeJSON(TypeDecorator):
    """Portable, crash-proof JSON column.

    * SQLite stores TEXT, PostgreSQL stores JSONB — same model definition.
    * Serialisation goes through :func:`json.dumps(..., default=str)`, so a
      stray ``date``/``datetime``/``Decimal`` inside a payload can never blow
      up a flush half way through a plan generation (no partial writes).
    * Values always read back as plain Python objects (dict/list/None).
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect is not None and dialect.name == "postgresql":
            # JSONB driver wants the object; make it JSON-safe first.
            return json.loads(json.dumps(value, ensure_ascii=False, default=str))
        return json.dumps(value, ensure_ascii=False, default=str)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None


# Backwards-compatible alias used across the models module.
JSONType = SafeJSON


def resolve_database_url() -> str:
    url = os.environ.get("STUDYS459_DATABASE_URL")
    if url:
        return url
    path = os.environ.get("STUDYS459_DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return f"sqlite:///{path}"


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        url = resolve_database_url()
        kwargs: dict[str, Any] = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            _apply_sqlite_pragmas(_engine)
    return _engine


def _apply_sqlite_pragmas(engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _record):  # pragma: no cover - driver level
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.commit()
        cursor.close()


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope - commits on success, rolls back on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db(drop: bool = False) -> None:
    from . import models  # noqa: F401  (registers metadata)
    from .migrations import sync_schema

    engine = get_engine()
    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    if not drop:
        # additive only: keeps a V3 database usable after the V3.1 upgrade
        sync_schema(engine)


def reset_engine() -> None:
    """Testing helper: forget cached engine/session factory."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def loads(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None
