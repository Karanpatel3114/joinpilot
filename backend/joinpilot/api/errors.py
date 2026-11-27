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


HTTP_CODES = {404: "NOT_FOUND", 409: "CONFLICT", 413: "PAYLOAD_TOO_LARGE", 429: "RATE_LIMITED"}


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    """Framework errors (unknown routes, wrong methods, malformed bodies) in the contract's
    shape: client errors keep a client code and their headers, such as `Allow` on 405."""
    assert isinstance(exc, StarletteHTTPException)
    status = exc.status_code
    code = "INTERNAL_ERROR" if status >= 500 else HTTP_CODES.get(status, "INVALID_INPUT")
    message = "There is nothing at this address." if status == 404 else str(exc.detail)
    response = error_response(status, code, message, {})
    response.headers.update(exc.headers or {})
    return response


async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unexpected error", exc_info=exc)
    return error_response(500, "INTERNAL_ERROR", "Something went wrong on the server.", {})


def install_error_handlers(app: FastAPI) -> None:
    """Register handlers so every error response uses the same JSON shape."""
    app.add_exception_handler(JoinPilotError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
