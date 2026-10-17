"""
Minimal in-process sliding-window rate limiter used as a FastAPI dependency.

This protects auth and public candidate endpoints from brute force on a single
instance. For multi-instance deployments put a shared limiter (e.g. at the
ingress / API gateway or a Redis-backed limiter) in front as well.
"""

import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import RateLimitedError


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0, scope: str = "default"):
        self.limit = limit
        self.window = window_seconds
        self.scope = scope
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "?")
        return f"{self.scope}:{ip}"

    async def __call__(self, request: Request) -> None:
        if self.limit <= 0:
            return
        now = time.monotonic()
        hits = self._hits[self._key(request)]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            raise RateLimitedError("Too many requests. Please slow down and try again shortly.")
        hits.append(now)
        # Opportunistic cleanup so the dict can't grow unbounded
        if len(self._hits) > 10_000:
            for key in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                self._hits.pop(key, None)
