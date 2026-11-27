"""Rate and request-size limits, enforced before a request reaches any endpoint.

Each client (IP address; behind a proxy, the hop the proxy added) gets a
per-minute request budget. Starting a run and asking a question use the language
model, so they also have per-minute and per-day budgets per client and a global
daily budget that protects the free model quota. JSON bodies are capped in size;
uploads have their own, larger limit. Counters live in memory, which fits the
single API process this app runs as (D-035).
"""

from __future__ import annotations

import ipaddress
import json
import re
import threading
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from joinpilot.config import Settings

EXPENSIVE = re.compile(r"^/projects/[^/]+/(runs|ask)$")
UPLOAD = re.compile(r"^/projects/[^/]+/tables$")
STORAGE = re.compile(r"^/projects(/[^/]+/tables)?$")
MINUTE, HOUR, DAY = 60.0, 3_600.0, 86_400.0
# Most windows kept; finished ones are pruned first, then the oldest are dropped
MAX_WINDOWS = 50_000
# Seconds between full prunes, so a full table never costs a scan on every request
PRUNE_EVERY = 5.0

Rule = tuple[str, int, float]


class Counter:
    """Fixed-window counters: at most `limit` hits per `period` seconds for each key."""

    def __init__(self) -> None:
        self._windows: dict[tuple[str, float], tuple[float, int]] = {}
        self._lock = threading.Lock()
        self._pruned_at = float("-inf")

    def hit(self, key: str, limit: int, period: float, now: float) -> float | None:
        """Count one hit; return seconds to wait when the window is already full."""
        refused = self.hit_all([(key, limit, period)], now)
        return None if refused is None else refused[1]

    def hit_all(self, rules: list[Rule], now: float) -> tuple[Rule, float] | None:
        """Count one hit against every rule, or none if any rule is full.

        Returns the first full rule and the seconds to wait. Checking before counting
        means a refused request uses no budget and creates no new window.
        """
        with self._lock:
            current = []
            for key, limit, period in rules:
                start, count = self._windows.get((key, period), (now, 0))
                if now - start >= period:
                    start, count = now, 0
                if count >= limit:
                    return (key, limit, period), period - (now - start)
                current.append(((key, period), start, count))
            for window, start, count in current:
                self._windows.pop(window, None)  # re-insert, so the dict stays oldest-first
                self._windows[window] = (start, count + 1)
            self._bound(now)
            return None

    def _bound(self, now: float) -> None:
        """Keep at most MAX_WINDOWS windows, so many clients cannot grow memory without end."""
        if len(self._windows) <= MAX_WINDOWS:
            return
        if now - self._pruned_at >= PRUNE_EVERY:
            self._pruned_at = now
            for (key, period), (start, _) in list(self._windows.items()):
                if now - start >= period:
                    del self._windows[(key, period)]
        while len(self._windows) > MAX_WINDOWS:
            del self._windows[next(iter(self._windows))]


def client_address(scope: Scope, hops: int) -> str:
    """The client's IP address.

    With `hops` trusted proxies in front (Render has one), the address is the entry
    those proxies appended to X-Forwarded-For, counted from the right; entries further
    left are written by the client and could be faked. Without proxies it is the peer.
    """
    peer = str((scope.get("client") or ("unknown", 0))[0])
    if hops <= 0:
        return client_key(peer)
    header = dict(scope["headers"]).get(b"x-forwarded-for", b"").decode("latin-1")
    hops_seen = [part.strip() for part in header.split(",") if part.strip()]
    return client_key(hops_seen[-hops] if len(hops_seen) >= hops else peer)


def client_key(address: str) -> str:
    """The budget an address counts against: IPv4 as is, IPv6 by its /64 network.

    One IPv6 subscriber usually gets a whole /64, so counting single addresses would
    give one visitor billions of separate budgets.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, 64), strict=False))
    return str(ip)


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
        client = client_address(scope, limits.forwarded_hops)
        rules: list[Rule] = [(client, limits.requests_per_minute, MINUTE)]
        if scope["method"] == "POST" and EXPENSIVE.match(path):
            rules = [
                ("model:everyone", limits.expensive_global_per_day, DAY),
                *rules,
                (f"model:{client}", limits.expensive_per_minute, MINUTE),
                (f"model:{client}", limits.expensive_per_day, DAY),
            ]
        if scope["method"] == "POST" and STORAGE.match(path):
            rules.append((f"storage:{client}", limits.storage_per_hour, HOUR))
        if (refused := self.counter.hit_all(rules, time.monotonic())) is not None:
            (key, _, period), wait = refused
            await refuse(send, 429, "RATE_LIMITED", too_many(key, period), wait)
            return
        cap = self.settings.max_upload_bytes if UPLOAD.match(path) else limits.max_body_kb * 1024
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and length.isdigit():
            if int(length) > cap:
                await refuse(send, 413, "PAYLOAD_TOO_LARGE", TOO_LARGE, None)
                return
            await self.app(scope, receive, send)
            return
        # No length (a chunked body): read it up to the cap first, then hand it on.
        body = await read_capped(receive, cap)
        if body is None:
            await refuse(send, 413, "PAYLOAD_TOO_LARGE", TOO_LARGE, None)
            return
        await self.app(scope, replay(body, receive), send)


TOO_LARGE = "The request body is too large."


def too_many(key: str, period: float) -> str:
    """A plain explanation of which budget ran out."""
    if key == "model:everyone":
        return "Today's budget of model-backed requests is used up; please try again tomorrow."
    if key.startswith("storage:"):
        return "Too many projects and uploads this hour; please wait and try again."
    if key.startswith("model:"):
        span = "minute" if period == MINUTE else "day"
        return f"Too many runs and questions this {span}; please wait and try again."
    return "Too many requests; please slow down."


async def read_capped(receive: Receive, cap: int) -> list[Message] | None:
    """The body's messages, or None once the body passes `cap` bytes."""
    messages: list[Message] = []
    seen = 0
    while True:
        message = await receive()
        messages.append(message)
        if message["type"] != "http.request":
            return messages
        seen += len(message.get("body", b""))
        if seen > cap:
            return None
        if not message.get("more_body", False):
            return messages


def replay(messages: list[Message], receive: Receive) -> Receive:
    """A receive channel that first returns the messages already read."""
    pending = list(messages)

    async def wrapped() -> Message:
        return pending.pop(0) if pending else await receive()

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
