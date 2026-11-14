"""A small in-memory sliding-window rate limiter keyed by client IP.

It is per process, which is enough for a single server. Behind a proxy, run uvicorn
with --proxy-headers so request.client.host is the real client address.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

from app.core.errors import AppError

_MAX_KEYS = 10_000


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, bucket: str, client: str, limit: int, window: float) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > _MAX_KEYS:
                self._hits = {
                    k: v for k, v in self._hits.items() if v and now - v[-1] < window
                }
            hits = self._hits.setdefault((bucket, client), deque())
            while hits and now - hits[0] >= window:
                hits.popleft()
            if len(hits) >= limit:
                wait = math.ceil(window - (now - hits[0]))
                raise RateLimited(
                    f"Too many requests from your address. Try again in {wait} seconds."
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def rate_limit(bucket: str, rule: tuple[int, int]) -> Callable[[Request], None]:
    limit, window = rule

    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        limiter.check(bucket, client, limit, window)

    return dependency
