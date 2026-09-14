"""Standard error envelope + application error type.

Contract (all non-2xx JSON responses):
    {"error": {"code": "<machine_code>", "message": "<human message>",
               "details": <optional extra data or null>}}

Success (2xx) responses return the payload directly (no envelope).
"""

from typing import Any


class AppError(Exception):
    """Raised by services/routes for expected failures (4xx-style).

    Attributes:
        code: stable machine-readable code, e.g. "insufficient_questions".
        message: human-readable message (user-facing, keep clear).
        status_code: HTTP status to return.
        details: optional extra structured data (counts, hints, ...).
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_envelope(code: str, message: str, details: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}
