from collections import OrderedDict

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from sentio.shared.utils import RateLimiter


class BodyLimitMiddleware:
    """Bound actual bytes before JSON parsing or multipart disk spooling."""

    def __init__(self, app, json_limit=2 * 1024 * 1024, upload_limit=24 * 1024 * 1024):
        self.app = app
        self.json_limit = json_limit
        self.upload_limit = upload_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        limit = (
            self.upload_limit
            if path.endswith(("/documents/upload", "/documents/jobs"))
            else self.json_limit
        )
        headers = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                length = int(declared)
                if length < 0:
                    raise ValueError()
            except ValueError:
                response = JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)
                return await response(scope, receive, send)
            if length > limit:
                response = JSONResponse(
                    {"detail": "Request body exceeds the allowed size."}, status_code=413
                )
                return await response(scope, receive, send)
        consumed = 0

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    raise HTTPException(413, "Request body exceeds the allowed size.")
            return message

        await self.app(scope, bounded_receive, send)


class ResponseHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def protected_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                    (b"content-security-policy", b"frame-ancestors 'none'"),
                ]
                if scope.get("path", "").startswith("/api/"):
                    message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        await self.app(scope, receive, protected_send)


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
        auth = not read and path.startswith("/api/v1/auth/")
        key = (client_ip, "auth" if auth else "read" if read else "write")
        if key not in self.limiters:
            if len(self.limiters) >= 4096:
                self.limiters.popitem(last=False)
            self.limiters[key] = RateLimiter(
                rate=self.rate * (0.1 if auth else 10 if read else 1),
                burst=min(self.burst, 10) if auth else self.burst,
            )
        self.limiters.move_to_end(key)

        if not self.limiters[key].allow():
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Retry shortly."},
                headers={"Retry-After": str(self.limiters[key].retry_after())},
            )

        return await call_next(request)
