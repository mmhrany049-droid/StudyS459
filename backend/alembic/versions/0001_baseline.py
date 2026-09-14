"""baseline (Phase 0: no tables yet — proves the migration chain works).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-14
"""
from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass  # Real tables arrive with Phase 1+ migrations.


def downgrade() -> None:
    pass
