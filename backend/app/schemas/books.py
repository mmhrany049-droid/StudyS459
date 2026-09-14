"""Book Engine response schemas (spec 14)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SubjectOut(BaseModel):
    id: int
    name: str
    grade: int
    track: str
    type: str  # noqa: A003 — matches spec 04 column name


class BookOut(BaseModel):
    id: int
    stable_key: str
    title: str
    publisher: str
    edition: str
    config_version: int
    grade: int
    track: str
    subject: SubjectOut
    active: bool
    activated_at: datetime | None
    node_count: int
    test_set_count: int
    question_count: int


# Detail currently equals list item (tree lives in a dedicated endpoint).
BookDetailOut = BookOut


class TestSetSummaryOut(BaseModel):
    id: int
    title: str
    test_type: str
    node_id: int | None
    question_count: int
    meta: dict[str, Any] = Field(default_factory=dict)


class TreeNodeOut(BaseModel):
    id: int
    parent_id: int | None
    node_type: str
    title: str
    code: str
    order_index: int
    is_leaf: bool
    meta: dict[str, Any] = Field(default_factory=dict)
    test_sets: list[TestSetSummaryOut] = Field(default_factory=list)
    children: list["TreeNodeOut"] = Field(default_factory=list)


TreeNodeOut.model_rebuild()


class BookTreeOut(BaseModel):
    book_id: int
    nodes: list[TreeNodeOut]


class ChildNodeOut(BaseModel):
    id: int
    parent_id: int | None
    node_type: str
    title: str
    code: str
    order_index: int
    is_leaf: bool
    meta: dict[str, Any] = Field(default_factory=dict)
    test_sets: list[TestSetSummaryOut] = Field(default_factory=list)


class NodeChildrenOut(BaseModel):
    node_id: int
    children: list[ChildNodeOut]


class ActivationOut(BaseModel):
    user_id: int
    book_id: int
    active: bool
    activated_at: datetime


class ImportOut(BaseModel):
    status: Literal["imported", "unchanged"]
    book_id: int
    stable_key: str
    node_count: int
    test_set_count: int
    question_count: int
