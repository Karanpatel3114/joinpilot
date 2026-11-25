"""Map domain errors and validation errors to the contract's error body."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from joinpilot.api.schemas import ErrorDetail, ErrorResponse
from joinpilot.errors import JoinPilotError

logger = logging.getLogger(__name__)


def error_response(
    status: int, code: str, message: str, details: dict[str, object]
) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))
    return JSONResponse(status_code=status, content=body.model_dump())


async def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, JoinPilotError)
    if exc.http_status >= 500:
        logger.exception("unhandled domain error", exc_info=exc)
    return error_response(exc.http_status, exc.code, exc.message, exc.details)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [".".join(str(part) for part in err["loc"]) for err in exc.errors()]
    return error_response(422, "INVALID_INPUT", "The request is not valid.", {"fields": fields})


def install_error_handlers(app: FastAPI) -> None:
    """Register handlers so every error response uses the same JSON shape."""
    app.add_exception_handler(JoinPilotError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
