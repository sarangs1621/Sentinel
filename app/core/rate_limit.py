import time

import jwt
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.core.security import TokenType, decode_token
from app.services.cache import CacheService

AUTH_PATHS = {
    f"{settings.API_V1_PREFIX}/auth/login",
    f"{settings.API_V1_PREFIX}/auth/register",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed fixed-window rate limiter for `/api/v1` requests.

    Identifies callers by the `sub` of a valid access token, falling back to
    client IP for unauthenticated requests. Fails open (allows the request)
    if Redis is unreachable, via `CacheService.check_rate_limit`.

    `/auth/login` and `/auth/register` use a separate, much tighter limit
    (`AUTH_RATE_LIMIT_*` settings) to slow down credential-stuffing/registration
    abuse, tracked independently of the general per-`/api/v1` limit.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.RATE_LIMIT_ENABLED or not request.url.path.startswith(settings.API_V1_PREFIX):
            return await call_next(request)

        identity = self._identify(request)
        if request.url.path in AUTH_PATHS:
            limit, window, prefix = (
                settings.AUTH_RATE_LIMIT_REQUESTS,
                settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
                "ratelimit:auth",
            )
        else:
            limit, window, prefix = (
                settings.RATE_LIMIT_REQUESTS,
                settings.RATE_LIMIT_WINDOW_SECONDS,
                "ratelimit",
            )

        bucket = int(time.time() // window)
        key = f"{prefix}:{identity}:{bucket}"

        cache = CacheService()
        allowed, retry_after = await cache.check_rate_limit(key, limit, window)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    @staticmethod
    def _identify(request: Request) -> str:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ")
            try:
                payload = decode_token(token)
                if payload.get("type") == TokenType.ACCESS.value:
                    return f"user:{payload['sub']}"
            except jwt.PyJWTError:
                pass

        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
