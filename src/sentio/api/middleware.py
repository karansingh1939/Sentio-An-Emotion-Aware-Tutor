from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from sentio.shared.utils import RateLimiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate: float = 1.0, burst: float = 60.0):
        super().__init__(app)
        self.rate = rate
        self.burst = burst
        self.limiters = {}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Bypass rate limiting for health, websockets, root and static assets
        if path.endswith(("/health", "/ws")) or "/static" in path or path == "/":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        if client_ip not in self.limiters:
            self.limiters[client_ip] = RateLimiter(rate=self.rate, burst=self.burst)

        if not self.limiters[client_ip].allow():
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Rate limit exceeded (max 60/min)."},
            )

        return await call_next(request)
