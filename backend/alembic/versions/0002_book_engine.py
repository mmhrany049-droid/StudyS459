"""book engine tables + default single user (Phase 1, spec 04).

Revision ID: 0002_book_engine
Revises: 0001_baseline
Create Date: 2026-09-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_book_engine"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("total_points", sa.Integer(), nullable=False),
        sa.Column("current_streak", sa.Integer(), nullable=False),
        sa.Column("longest_streak", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "grade", "track", name="uq_subject_name_grade_track"),
    )
    op.create_index("ix_subjects_name", "subjects", ["name"])

    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stable_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("publisher", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("track", sa.String(length=64), nullable=False),
        sa.Column("edition", sa.String(length=64), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_books_stable_key", "books", ["stable_key"], unique=True)
    op.create_index("ix_books_subject_id", "books", ["subject_id"])

    op.create_table(
        "user_book_activations",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "book_id"),
    )

    op.create_table(
        "book_nodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["book_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_book_nodes_book_id", "book_nodes", ["book_id"])
    op.create_index("ix_book_nodes_parent_id", "book_nodes", ["parent_id"])
    op.create_index("ix_book_nodes_node_type", "book_nodes", ["node_type"])
    op.create_index("ix_book_nodes_code", "book_nodes", ["code"])

    op.create_table(
        "test_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("test_type", sa.String(length=32), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["node_id"], ["book_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_sets_book_id", "test_sets", ["book_id"])
    op.create_index("ix_test_sets_test_type", "test_sets", ["test_type"])
    op.create_index("ix_test_sets_node_id", "test_sets", ["node_id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("stable_key", sa.String(length=256), nullable=False),
        sa.Column("test_set_id", sa.Integer(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("difficulty_level", sa.String(length=32), nullable=True),
        sa.Column("answer_type", sa.String(length=32), nullable=False),
        sa.Column("answer_key", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["test_set_id"], ["test_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", "stable_key", name="uq_question_book_stable_key"),
        sa.UniqueConstraint("test_set_id", "sequence_no", name="uq_question_testset_sequence"),
    )
    op.create_index("ix_questions_book_id", "questions", ["book_id"])
    op.create_index("ix_questions_stable_key", "questions", ["stable_key"])
    op.create_index("ix_questions_test_set_id", "questions", ["test_set_id"])
    op.create_index("ix_questions_sequence_no", "questions", ["sequence_no"])
    op.create_index("ix_questions_difficulty_level", "questions", ["difficulty_level"])

    op.create_table(
        "question_topic_map",
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["book_nodes.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.PrimaryKeyConstraint("question_id", "node_id"),
    )
    op.create_index("ix_question_topic_map_node", "question_topic_map", ["node_id"])

    op.create_table(
        "book_imports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_book_imports_book_id", "book_imports", ["book_id"])
    op.create_index("ix_book_imports_config_hash", "book_imports", ["config_hash"])

    # Seed the default single user (self-contained: plain Core insert).
    users = sa.table(
        "users",
        sa.column("id"),
        sa.column("username"),
        sa.column("display_name"),
        sa.column("grade"),
        sa.column("track"),
        sa.column("timezone"),
        sa.column("total_points"),
        sa.column("current_streak"),
        sa.column("longest_streak"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    bind = op.get_bind()
    exists = bind.execute(sa.select(sa.func.count()).select_from(users).where(users.c.id == 1)).scalar()
    if not exists:
        now = sa.func.now()  # DB-side timestamp keeps it portable
        bind.execute(
            users.insert().values(
                id=1,
                username="student",
                display_name="دانش‌آموز",
                grade=11,
                track="mathematics",
                timezone="Asia/Tehran",
                total_points=0,
                current_streak=0,
                longest_streak=0,
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_table("book_imports")
    op.drop_table("question_topic_map")
    op.drop_table("questions")
    op.drop_table("test_sets")
    op.drop_table("book_nodes")
    op.drop_table("user_book_activations")
    op.drop_table("books")
    op.drop_table("subjects")
    op.drop_table("users")
