"""Reward request/response schemas (spec 14 rewards section)."""

from datetime import datetime

from pydantic import BaseModel


class BadgeOut(BaseModel):
    code: str
    title: str
    description: str | None
    earned: bool
    earned_at: datetime | None


class RewardEventOut(BaseModel):
    id: int
    event_type: str
    points: int
    description: str | None
    related_entity_type: str | None
    related_entity_id: int | None
    created_at: datetime


class RewardsSummaryOut(BaseModel):
    user_id: int
    total_points: int
    current_streak: int
    longest_streak: int
    badge_count: int
    badges: list[BadgeOut]  # earned, most recent first
    recent_events: list[RewardEventOut]
