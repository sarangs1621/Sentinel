import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import (
    AccountLockedError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.core.redis import get_redis_client
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.sentry import configure_sentry
from app.db.session import AsyncSessionLocal

configure_logging()
configure_sentry()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(request: Request, exc: PermissionDeniedError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(AccountLockedError)
    async def account_locked_handler(request: Request, exc: AccountLockedError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_423_LOCKED, content={"detail": str(exc)})


logger = logging.getLogger(__name__)

async def local_scheduler_loop() -> None:
    from app.core.config import settings
    from app.workers.tasks import (
        _get_due_monitor_ids,
        _perform_check,
        _get_due_notification_ids,
        _deliver_notification,
        _get_aggregation_monitor_ids,
        _aggregate_monitor_metrics,
        _yesterday_utc_midnight
    )
    
    logger.info("Scheduler started. Running in-process background task.")
    
    last_check = 0.0
    last_metrics = 0.0

    check_interval = settings.CHECK_DISPATCH_INTERVAL_SECONDS
    metrics_interval = settings.METRICS_AGGREGATION_INTERVAL_SECONDS

    while True:
        try:
            now = time.time()
            
            if now - last_check >= check_interval:
                monitor_ids = await _get_due_monitor_ids()
                for m_id in monitor_ids:
                    asyncio.create_task(_perform_check(m_id))
                    
                notification_ids = await _get_due_notification_ids()
                for n_id in notification_ids:
                    asyncio.create_task(_deliver_notification(n_id))
                    
                last_check = now
                
            if now - last_metrics >= metrics_interval:
                monitor_ids = await _get_aggregation_monitor_ids()
                period_start = _yesterday_utc_midnight()
                for m_id in monitor_ids:
                    asyncio.create_task(_aggregate_monitor_metrics(m_id, period_start))
                    
                last_metrics = now

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_task = asyncio.create_task(local_scheduler_loop())
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key"],
        )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def readiness_check() -> JSONResponse:
        checks = {"database": "ok", "redis": "ok"}

        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            checks["database"] = "error"

        try:
            await get_redis_client().ping()
        except RedisError:
            checks["redis"] = "error"

        is_ready = all(value == "ok" for value in checks.values())
        status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=status_code, content={"status": "ok" if is_ready else "error", **checks})

    return app


app = create_app()
