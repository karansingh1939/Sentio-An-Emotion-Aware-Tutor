from collections import OrderedDict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from sentio.shared.utils import RateLimiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate: float = 1.0, burst: float = 60.0):
        super().__init__(app)
        self.rate = rate
        self.burst = burst
        self.limiters = OrderedDict()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Bypass rate limiting for health, websockets, root and static assets
        if path.endswith(("/health", "/ws")) or "/static" in path or path == "/":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        # Browsing and job polling must not consume the submission/login budget.
        read = request.method in {"GET", "HEAD", "OPTIONS"}
        key = (client_ip, "read" if read else "write")
        if key not in self.limiters:
            if len(self.limiters) >= 4096:
                self.limiters.popitem(last=False)
            self.limiters[key] = RateLimiter(rate=self.rate * (10 if read else 1), burst=self.burst)
        self.limiters.move_to_end(key)

        if not self.limiters[key].allow():
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Retry shortly."},
                headers={"Retry-After": "1"},
            )

        return await call_next(request)
