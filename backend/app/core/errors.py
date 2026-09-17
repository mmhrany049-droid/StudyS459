"""Domain errors.

Business rules must never be silently swallowed and must never be enforced in
the UI layer; services raise these and the API layer translates them into a
clear Persian message plus a machine readable code.
"""

from __future__ import annotations

from typing import Any, Optional


class DomainError(Exception):
    code = "domain_error"
    http_status = 400

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class NotFoundError(DomainError):
    code = "not_found"
    http_status = 404


class ValidationError(DomainError):
    code = "validation_error"
    http_status = 422


class ConflictError(DomainError):
    code = "conflict"
    http_status = 409


class InsufficientPoolError(DomainError):
    """Not enough questions for the requested range/parity combination."""

    code = "insufficient_questions"
    http_status = 409


class CycleError(DomainError):
    code = "dependency_cycle"
    http_status = 409


class MissingAnswerKeyError(DomainError):
    code = "missing_answer_key"
    http_status = 409


class ImmutableError(DomainError):
    code = "immutable"
    http_status = 409
