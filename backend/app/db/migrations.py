"""Additive schema migration (V3 → V3.1).

V3 law: *never delete user data*. Upgrading an existing V3 database must add what
V3.1 needs and leave every row (attempts, exams, plans, taught marks) untouched.

`Base.metadata.create_all` creates missing **tables** but silently ignores missing
**columns**, so a V3 database would keep a stale `exams` table after V3.1 adds
`subjects`. This module closes that gap:

* missing tables  → created by `create_all` (see :func:`init_db`);
* missing columns → `ALTER TABLE ... ADD COLUMN` here.

Only additions are ever emitted. Nothing is dropped, renamed or rewritten, and a
column that already exists is skipped, so the function is idempotent and safe to
run on every start.
"""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# SQLite cannot add a NOT NULL column without a default; for those (rare) cases we
# add the column as nullable and let the ORM default apply to new rows.
_UNSAFE_DEFAULTS = {"CURRENT_TIMESTAMP"}


def _column_ddl(table_name: str, column, dialect) -> str:
    column_type = column.type.compile(dialect=dialect)
    ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {column_type}'
    if column.server_default is not None:
        default_sql = str(getattr(column.server_default, "arg", "") or "")
        if default_sql and default_sql.upper() not in _UNSAFE_DEFAULTS:
            ddl += f" DEFAULT {default_sql}"
            if not column.nullable:
                ddl += " NOT NULL"
    return ddl


def missing_columns(engine: Engine) -> Dict[str, List[str]]:
    """Return ``{table: [column, ...]}`` for columns the database is missing."""
    from .base import Base  # local import: avoids a circular import at module load

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing: Dict[str, List[str]] = {}
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all will build it
        present = {column["name"] for column in inspector.get_columns(table.name)}
        absent = [column.name for column in table.columns if column.name not in present]
        if absent:
            missing[table.name] = absent
    return missing


def sync_schema(engine: Engine) -> Dict[str, List[str]]:
    """Apply additive DDL so an existing database matches the current models."""
    from .base import Base

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    applied: Dict[str, List[str]] = {}
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {column["name"] for column in inspector.get_columns(table.name)}
            added: List[str] = []
            for column in table.columns:
                if column.name in present:
                    continue
                connection.execute(text(_column_ddl(table.name, column, engine.dialect)))
                added.append(column.name)
            if added:
                applied[table.name] = added
    return applied
