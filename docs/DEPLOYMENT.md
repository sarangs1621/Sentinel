# Deployment Guide

## Environment Variables

All configuration is read by `app/core/config.py` (Pydantic `Settings`),
sourced from a `.env` file (see `.env.example`) or real environment
variables. Validation runs at startup — the app refuses to boot with an
invalid configuration.

| Variable | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | `testing` relaxes the `SECRET_KEY` length check |
| `PROJECT_NAME` | `Sentinel` | Used as the FastAPI app title |
| `API_V1_PREFIX` | `/api/v1` | Prefix for all versioned routes and the OpenAPI schema |
| `BACKEND_CORS_ORIGINS` | `[]` | JSON list or comma-separated string of allowed origins. **Must not contain `"*"`** — validated and rejected at startup. CORS middleware is only registered if this is non-empty |
| `SECRET_KEY` | — (required) | JWT signing key. Must be ≥32 chars unless `ENVIRONMENT=testing`. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime; `refresh_tokens.id` doubles as the JWT `jti` |
| `DATABASE_URL` | — (required) | `postgresql+asyncpg://user:pass@host:port/db` |
| `TEST_DATABASE_URL` | `None` | Separate database used by the test suite |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `sentinel` / `sentinel` / `sentinel` | Used by Docker Compose to provision the `db` service |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` | Used when constructing connection strings outside Docker |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker + result backend, app cache, rate limiting, JWT denylist |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | `true` runs Celery tasks synchronously in-process — useful for local dev/tests without Redis |
| `CHECK_DISPATCH_INTERVAL_SECONDS` | `10.0` | How often Beat dispatches `dispatch_due_checks` and `dispatch_pending_notifications` |
| `METRICS_AGGREGATION_INTERVAL_SECONDS` | `3600.0` | How often Beat dispatches `aggregate_monitor_metrics` |
| `RATE_LIMIT_ENABLED` | `true` | Toggle `RateLimitMiddleware` |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | `100` / `60` | General fixed-window limiter |
| `AUTH_RATE_LIMIT_REQUESTS` / `AUTH_RATE_LIMIT_WINDOW_SECONDS` | `5` / `60` | Stricter limiter for `/auth/login` and `/auth/register` |
| `MAX_LOGIN_FAILURES` / `LOGIN_LOCKOUT_WINDOW_SECONDS` | `5` / `900` | Account lockout after repeated failed logins for the same email |
| `MAX_REQUEST_BODY_BYTES` | `1048576` (1 MiB) | Requests over this size get `413` from `SecurityHeadersMiddleware` |
| `HSTS_MAX_AGE_SECONDS` | `63072000` (2 years) | `Strict-Transport-Security` header value |
| `SMTP_HOST` / `SMTP_PORT` | `localhost` / `587` | Email alert delivery via `aiosmtplib` |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | `None` | SMTP auth (optional) |
| `SMTP_USE_TLS` | `true` | STARTTLS for SMTP |
| `SMTP_FROM_ADDRESS` | `alerts@sentinel.local` | `From` address for email alerts |

## Docker Setup

`docker-compose.yml` defines five services:

| Service | Image / Build | Purpose |
|---|---|---|
| `db` | `postgres:16-alpine` | Primary database, healthcheck via `pg_isready` |
| `redis` | `redis:7-alpine` | Celery broker/result backend + app cache, healthcheck via `redis-cli ping` |
| `api` | built from `Dockerfile` | FastAPI app, runs `alembic upgrade head` then `uvicorn` |
| `worker` | built from `Dockerfile` | `celery -A app.core.celery_app worker --loglevel=info` |
| `beat` | built from `Dockerfile` | `celery -A app.core.celery_app beat --loglevel=info` |

`api`, `worker`, and `beat` all load `.env` via `env_file`, then override
`DATABASE_URL` (pointing at the `db` service), `REDIS_URL` (pointing at the
`redis` service), and set `CELERY_TASK_ALWAYS_EAGER=false`. `api` and
`worker`/`beat` both wait for `db`/`redis` to report healthy before
starting.

The `Dockerfile` is a two-stage build:

1. **`builder`** (`python:3.12-slim`) — creates a venv at `/opt/venv` and
   installs `requirements.txt`.
2. **`runtime`** (`python:3.12-slim`) — copies only the venv,
   `alembic.ini`, `alembic/`, and `app/` into the image, runs as a
   non-root `app` user, and exposes port `8000`.

Start everything:

```bash
cp .env.example .env
docker compose up -d
docker compose ps        # check health status
docker compose logs -f api
```

## Database Migration Process

Migrations are managed with Alembic (`alembic/versions/`).

- **Apply migrations** (done automatically by the `api` container on
  startup, and required before running locally without Docker):

  ```bash
  alembic upgrade head
  ```

- **Create a new migration** after changing a model in `app/models/`:

  ```bash
  alembic revision --autogenerate -m "describe the change"
  ```

  Review the generated file in `alembic/versions/` before committing —
  autogenerate doesn't always detect things like check constraints or
  partial indexes correctly (Sentinel's soft-delete partial unique index
  and the migration-0008 query indexes were hand-verified).

- **Roll back one revision**:

  ```bash
  alembic downgrade -1
  ```

## Worker Startup

The Monitoring/Notification/Analytics engines run as Celery tasks,
scheduled by Celery Beat (`app/core/celery_app.py`, `beat_schedule`):

| Periodic task | Interval | Does |
|---|---|---|
| `dispatch_due_checks` | `CHECK_DISPATCH_INTERVAL_SECONDS` (default 10s) | Queues `perform_check` for every active monitor whose `check_interval_seconds` has elapsed |
| `dispatch_pending_notifications` | `CHECK_DISPATCH_INTERVAL_SECONDS` | Queues `deliver_notification` for `pending`/retryable-`failed` notifications |
| `aggregate_monitor_metrics` (dispatcher) | `METRICS_AGGREGATION_INTERVAL_SECONDS` (default 3600s) | Queues a per-monitor aggregation task that upserts yesterday's `MetricSnapshot` |

Start a worker and beat process (requires Redis and
`CELERY_TASK_ALWAYS_EAGER=false`):

```bash
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app beat --loglevel=info
```

For local development/CI without Redis, set `CELERY_TASK_ALWAYS_EAGER=true`
— `.delay()`/`.apply_async()` calls execute the task function synchronously
in the calling process, so the same code path is exercised by tests without
a broker. Note that eager mode does **not** exercise broker/worker behavior
such as message serialization, broker-side scheduling, network delivery, or
broker-mediated retries/acks — validate those with a real broker/worker setup
or integration tests.

## Health Checks

- **App**: `GET /health` → `{"status": "ok"}`. Add this as a container/load
  balancer health check for the `api` service.
- **Postgres** (`db` service): `pg_isready -U $POSTGRES_USER`, every 5s,
  5 retries.
- **Redis** (`redis` service): `redis-cli ping`, every 5s, 5 retries.
- **OpenAPI**: `GET /api/v1/openapi.json` returning `200` confirms the app
  booted and registered all routers.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App fails to start: `SECRET_KEY must be at least 32 characters...` | `SECRET_KEY` missing/short in `.env` | Generate a real secret: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| App fails to start: `BACKEND_CORS_ORIGINS must not contain '*'` | `.env` has `BACKEND_CORS_ORIGINS=["*"]` | List explicit origins, e.g. `["http://localhost:3000"]` |
| CORS preflight missing `Access-Control-Allow-Origin` | `BACKEND_CORS_ORIGINS` is empty — `CORSMiddleware` is only added if the list is non-empty | Set `BACKEND_CORS_ORIGINS` to include your frontend origin |
| `alembic upgrade head` fails with connection refused | `DATABASE_URL` points at the wrong host/port, or Postgres isn't ready yet | In Docker, ensure `db` healthcheck passes first; locally, confirm Postgres is running on the configured port |
| Checks never run / monitors stay `pending` | `worker`/`beat` not running and `CELERY_TASK_ALWAYS_EAGER=false` | Start both Celery processes, or set `CELERY_TASK_ALWAYS_EAGER=true` for in-process execution |
| Webhook/email alerts never deliver | `worker`/`beat` not running, or `SMTP_*`/webhook target unreachable | Check `notifications` rows for `status=failed` + `error_message`; verify `SMTP_HOST`/credentials |
| Redis down but app still responds (just slower / unrate-limited) | Expected — cache, rate limiting, and the JWT denylist all fail open on `RedisError` | Restore Redis; no data is lost, but rate limiting and access-token revocation are temporarily inactive |
| `429 Too Many Requests` during local testing | `RATE_LIMIT_ENABLED=true` with default limits | Set `RATE_LIMIT_ENABLED=false` for local/dev/test environments (already set in CI) |
| Test suite hangs or fails to find a database | `TEST_DATABASE_URL` not set or test DB doesn't exist | `createdb sentinel_test`, set `TEST_DATABASE_URL` in `.env` |
