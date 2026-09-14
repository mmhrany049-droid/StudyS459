"""Shared FastAPI dependencies."""

from app.config import get_settings


def get_current_user_id() -> int:
    """Return the active user id.

    TEMPORARY Phase-0 scaffolding for the single-user MVP: the final auth
    method is an open decision (spec 18, #9) and must stay simple.
    Every future endpoint MUST use this (ownership rule, spec 14).
    """
    return get_settings().SINGLE_USER_ID
