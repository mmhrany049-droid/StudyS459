"""Database engine / session / declarative base (SQLAlchemy 2.x style).

- SQLite by default (single file, zero setup).
- PostgreSQL-ready: just point DATABASE_URL at postgres (+psycopg driver).
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


def utcnow() -> datetime:
    """Naive-UTC timestamp for DB storage.

    Single convention across SQLite and PostgreSQL: all datetimes are stored
    as naive UTC; conversion to the user-facing timezone (Asia/Tehran)
    happens at presentation time (Phase 1 stores, later phases present).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Declarative base for all ORM models (models arrive in Phase 1+)."""


def _ensure_sqlite_parent(url: str) -> None:
    # Only for file-based sqlite URLs like sqlite:///./ss459.db
    if url == "sqlite:///:memory:":
        return
    prefix = "sqlite:///"
    if url.startswith(prefix):
        path = url[len(prefix):]
        parent = Path(path).expanduser().parent
        parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    connect_args: dict = {}
    if url.startswith("sqlite"):
        _ensure_sqlite_parent(url)
        connect_args = {"check_same_thread": False}
    engine = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):
        # SQLite ignores FK constraints unless explicitly enabled per connection.
        @event.listens_for(engine, "connect")
        def _enforce_sqlite_fk(dbapi_connection, connection_record):  # noqa: D103, ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine: Engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
