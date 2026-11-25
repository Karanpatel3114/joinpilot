"""Domain errors.

Package code raises these; the API layer maps each one to an HTTP status and the
contract's error body `{"error": {"code", "message", "details"}}`.
"""

from __future__ import annotations

from typing import Any


class JoinPilotError(Exception):
    """Base error with a stable code, a plain-language message and details."""

    code = "INTERNAL_ERROR"
    http_status = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(JoinPilotError):
    """A project, table, run or other resource does not exist."""

    code = "NOT_FOUND"
    http_status = 404


class InvalidInputError(JoinPilotError):
    """The request is well-formed JSON but asks for something invalid."""

    code = "INVALID_INPUT"
    http_status = 422


class ConflictError(JoinPilotError):
    """The resource is in a state that does not allow this action."""

    code = "CONFLICT"
    http_status = 409


class LLMUnavailableError(JoinPilotError):
    """The language model could not answer (no key, quota, network or invalid output)."""

    code = "LLM_UNAVAILABLE"
    http_status = 503


class JobQueueUnavailableError(JoinPilotError):
    """A background job could not be queued (for example, Redis is down)."""

    code = "QUEUE_UNAVAILABLE"
    http_status = 503


class PayloadTooLargeError(JoinPilotError):
    """An upload or request body is larger than the configured limit."""

    code = "PAYLOAD_TOO_LARGE"
    http_status = 413
