"""Map domain errors and validation errors to the contract's error body."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    """Unknown routes and wrong methods, in the contract's error shape too."""
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code == 404:
        return error_response(404, "NOT_FOUND", "There is nothing at this address.", {})
    if exc.status_code == 405:
        return error_response(405, "INVALID_INPUT", "This method is not allowed here.", {})
    return error_response(exc.status_code, "INTERNAL_ERROR", str(exc.detail), {})


async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unexpected error", exc_info=exc)
    return error_response(500, "INTERNAL_ERROR", "Something went wrong on the server.", {})


def install_error_handlers(app: FastAPI) -> None:
    """Register handlers so every error response uses the same JSON shape."""
    app.add_exception_handler(JoinPilotError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
