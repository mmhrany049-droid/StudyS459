"""Alembic environment — URL always comes from app settings (single source)."""

import sys
from logging.config import fileConfig
from pathlib import Path

# Ensure `import app...` works regardless of how alembic is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db import Base  # noqa: F401  (ensures Base.metadata is the autogenerate target)

# Import all models so autogenerate sees their tables (Phase 1+).
from app import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    # `-x db_url=...` allows per-run override; default is app settings.
    x_args = context.get_x_argument(as_dictionary=True)
    if "db_url" in x_args:
        return x_args["db_url"]
    return get_settings().DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # sqlite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _get_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = engine_from_config(
        {"sqlalchemy.url": url, "sqlalchemy.connect_args": connect_args},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # sqlite ALTER TABLE support
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
