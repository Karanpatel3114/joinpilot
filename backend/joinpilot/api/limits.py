"""Rate and request-size limits, enforced before a request reaches any endpoint.

Each client (IP address, from the proxy's forwarded header in production) gets a
per-minute request budget. Starting a run and asking a question use the language
model, so they also have per-minute and per-day budgets per client and a global
daily budget that protects the free model quota. JSON bodies are capped in size;
uploads have their own, larger limit. Counters live in memory, which fits the
single API process this app runs as (D-035).
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import defaultdict
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from joinpilot.config import Settings
from joinpilot.errors import PayloadTooLargeError

EXPENSIVE = re.compile(r"^/projects/[^/]+/(runs|ask)$")
UPLOAD = re.compile(r"^/projects/[^/]+/tables$")
MINUTE, DAY = 60.0, 86_400.0
# Windows kept before finished ones are pruned
MAX_WINDOWS = 50_000


class Counter:
    """Fixed-window counters: at most `limit` hits per `period` seconds for each key."""

    def __init__(self) -> None:
        self._windows: dict[tuple[str, float], tuple[float, int]] = defaultdict(lambda: (0.0, 0))
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, period: float, now: float) -> float | None:
        """Count one hit; return seconds to wait when the window is already full."""
        with self._lock:
            if len(self._windows) > MAX_WINDOWS:
                self._prune(now)
            start, count = self._windows[(key, period)]
            if now - start >= period:
                start, count = now, 0
            if count >= limit:
                return period - (now - start)
            self._windows[(key, period)] = (start, count + 1)
            return None

    def _prune(self, now: float) -> None:
        """Forget finished windows, so many distinct clients cannot grow memory without end."""
        for (key, period), (start, _) in list(self._windows.items()):
            if now - start >= period:
                del self._windows[(key, period)]


class LimitMiddleware:
    """ASGI middleware applying the limits in `settings.limits`."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.counter = Counter()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/health" or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return
        limits, path = self.settings.limits, scope["path"]
        client = (scope.get("client") or ("unknown", 0))[0]
        now = time.monotonic()
        rules = [(client, limits.requests_per_minute, MINUTE)]
        if scope["method"] == "POST" and EXPENSIVE.match(path):
            rules += [
                (f"model:{client}", limits.expensive_per_minute, MINUTE),
                (f"model:{client}", limits.expensive_per_day, DAY),
                ("model:everyone", limits.expensive_global_per_day, DAY),
            ]
        for key, limit, period in rules:
            if (wait := self.counter.hit(key, limit, period, now)) is not None:
                await refuse(send, 429, "RATE_LIMITED", too_many(key, period), wait)
                return
        cap = self.settings.max_upload_bytes if UPLOAD.match(path) else limits.max_body_kb * 1024
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and length.isdigit() and int(length) > cap:
            await refuse(send, 413, "PAYLOAD_TOO_LARGE", "The request body is too large.", None)
            return
        await self.app(scope, capped(receive, cap), send)


def too_many(key: str, period: float) -> str:
    """A plain explanation of which budget ran out."""
    if key == "model:everyone":
        return "Today's budget of model-backed requests is used up; please try again tomorrow."
    if key.startswith("model:"):
        span = "minute" if period == MINUTE else "day"
        return f"Too many runs and questions this {span}; please wait and try again."
    return "Too many requests; please slow down."


def capped(receive: Receive, cap: int) -> Receive:
    """A receive channel that refuses bodies sent without a length once they pass `cap`."""
    seen = 0

    async def wrapped() -> Message:
        nonlocal seen
        message = await receive()
        if message["type"] == "http.request":
            seen += len(message.get("body", b""))
            if seen > cap:
                raise PayloadTooLargeError("The request body is too large.")
        return message

    return wrapped


async def refuse(
    send: Send, status: int, code: str, message: str, retry_after: float | None
) -> None:
    """Answer with the contract's error body without calling the app."""
    body: dict[str, Any] = {"error": {"code": code, "message": message, "details": {}}}
    headers = [(b"content-type", b"application/json")]
    if retry_after is not None:
        seconds = max(1, int(retry_after + 0.999))
        body["error"]["details"]["retry_after_seconds"] = seconds
        headers.append((b"retry-after", str(seconds).encode()))
    payload = json.dumps(body).encode()
    headers.append((b"content-length", str(len(payload)).encode()))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": payload})
