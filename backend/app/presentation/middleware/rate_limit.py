"""
Simple in-memory sliding-window rate limiter. Adequate for a single-instance
take-home deployment; the README documents swapping to Redis for multi-
instance production use (in-memory state doesn't share across replicas).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._settings = get_settings()
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        client_key = request.client.host if request.client else "unknown"
        now = time.time()
        window = self._hits[client_key]

        while window and now - window[0] > 60:
            window.popleft()

        if len(window) >= self._settings.rate_limit_requests_per_minute:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Please slow down."})

        window.append(now)
        return await call_next(request)
