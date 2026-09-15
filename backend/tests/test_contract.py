"""Contract compliance: every spec-14 URL (minus auth/telegram) is registered.

Auth stays a single-user stub (open decision #9); Telegram is out of v1.
"""

from app.main import create_app

# (method, path template) — path params as FastAPI spells them.
CONTRACT = [
    ("GET", "/health"),
    ("GET", "/health/db"),
    # Books
    ("GET", "/books"),
    ("GET", "/books/{book_id}"),
    ("POST", "/books/import"),
    ("POST", "/users/me/books/{book_id}/activate"),
    ("DELETE", "/users/me/books/{book_id}/activate"),
    # Nodes
    ("GET", "/books/{book_id}/nodes"),
    ("GET", "/nodes/{node_id}/children"),
    ("GET", "/nodes/{node_id}/parity-state"),
    # Tests
    ("POST", "/test-sessions"),
    ("GET", "/test-sessions/{session_id}"),
    ("POST", "/test-sessions/{session_id}/answers"),
    ("POST", "/test-sessions/{session_id}/finish"),
    ("GET", "/questions/{question_id}/history"),
    # Progress + analytics
    ("GET", "/progress/overview"),
    ("GET", "/progress/books/{book_id}"),
    ("GET", "/progress/nodes/{node_id}"),
    ("GET", "/progress/questions/{question_id}"),
    ("GET", "/analytics/trends"),
    ("GET", "/analytics/weaknesses"),
    # Goals
    ("GET", "/goals/weeks/{week}"),
    ("POST", "/goals/weeks/{week}"),
    ("PATCH", "/goals/{goal_id}"),
    ("GET", "/goals/{goal_id}/candidate-tasks"),
    # Planner
    ("GET", "/planner/day/{day}"),
    ("GET", "/planner/week/{week}"),
    ("POST", "/tasks"),
    ("PATCH", "/tasks/{task_id}"),
    ("POST", "/tasks/{task_id}/complete"),
    ("PUT", "/planner/placements"),
    # Academic
    ("GET", "/schedules"),
    ("POST", "/schedules"),
    ("POST", "/school-day-overrides"),
    ("GET", "/class-sessions"),
    ("POST", "/class-sessions"),
    ("GET", "/taught-lessons"),
    ("POST", "/taught-lessons"),
    ("GET", "/homework"),
    ("POST", "/homework"),
    ("PATCH", "/homework/{homework_id}"),
    # Exams
    ("GET", "/exams"),
    ("POST", "/exams"),
    ("GET", "/exams/{exam_id}"),
    ("POST", "/exams/{exam_id}/questions"),
    ("GET", "/exams/{exam_id}/analytics"),
    # Rewards
    ("GET", "/rewards/summary"),
    ("GET", "/rewards/events"),
    ("GET", "/rewards/badges"),
    # Users (Phase 8 settings)
    ("GET", "/users/me"),
    ("PATCH", "/users/me"),
]


def _registered() -> set[tuple[str, str]]:
    app = create_app()
    out: set[tuple[str, str]] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            out.add((method, path))
    return out


def test_contract_urls_registered() -> None:
    registered = _registered()
    missing = [c for c in CONTRACT if c not in registered]
    assert missing == []


def test_no_api_v1_prefix() -> None:
    """Contract URLs are exact: no /api/v1 prefix anywhere (standing rule)."""
    for _method, path in _registered():
        assert not path.startswith("/api/"), path
