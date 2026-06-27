# Sentinel

**Open-source uptime monitoring & incident management platform.**

Built with FastAPI, Next.js 15, PostgreSQL, Redis, and Celery — Sentinel provides real-time health checks, automated incident detection, alerting, analytics dashboards, and a full audit trail.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Docker Compose (Full Stack)](#docker-compose-full-stack)
  - [Local Postgres on Windows (No Docker)](#local-postgres-on-windows-no-docker)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [API Reference](#api-reference)
  - [Authentication](#authentication)
  - [Workspaces & Members](#workspaces--members)
  - [Monitors](#monitors)
  - [Health Checks & Incidents](#health-checks--incidents)
  - [Alert Rules & Notifications](#alert-rules--notifications)
  - [Analytics & Metrics](#analytics--metrics)
  - [Audit Logs](#audit-logs)
  - [System Health](#system-health)
- [Frontend Pages](#frontend-pages)
- [Scheduler & Background Workers](#scheduler--background-workers)
- [Testing](#testing)
- [CI/CD](#cicd)
- [Deployment](#deployment)
- [Git Workflow & Branch Naming](#git-workflow--branch-naming)
- [Documentation](#documentation)

---

## Features

- **Multi-protocol monitoring** — HTTP, TCP, and PING health checks with configurable intervals
- **Automated incident lifecycle** — Configurable failure thresholds trigger incidents; auto-recovery resolves them
- **Workspace-based multi-tenancy** — Isolated workspaces with invite codes and RBAC (owner/admin/member)
- **Alerting engine** — Webhook and email alert rules with severity filtering and retry logic
- **Analytics & SLA reporting** — Latency percentiles (p50/p95/p99), uptime %, daily metric snapshots
- **Audit logging** — Immutable, searchable logs with before/after diffs and request metadata (IP, user agent)
- **Dashboard** — Real-time workspace overview with monitor/incident status counts
- **Security hardened** — Rate limiting, CORS, security headers (HSTS, CSP, etc.), account lockout, secret key validation

---

## Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI** | Async REST API framework |
| **SQLAlchemy 2.0** (async) | ORM with asyncpg driver |
| **PostgreSQL** | Primary datastore |
| **Alembic** | Database migrations |
| **Celery + Redis** | Distributed task queue for health checks & notifications |
| **Pydantic v2** | Request/response validation and settings management |
| **Sentry** | Error tracking & performance monitoring (optional) |

### Frontend
| Technology | Purpose |
|---|---|
| **Next.js 15** | React framework with App Router |
| **React 19** | UI library |
| **TypeScript** | Type-safe frontend code |

### DevOps
| Technology | Purpose |
|---|---|
| **Docker** | Multi-stage production image |
| **Docker Compose** | Local full-stack orchestration |
| **GitHub Actions** | CI pipeline (lint, type check, test, security scan) |
| **Render** | Backend deployment (API + worker + beat) |
| **Vercel** | Frontend deployment |

---

## Architecture

Sentinel follows a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js Frontend                         │
│              (React 19 + TypeScript + App Router)           │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / REST
┌──────────────────────────▼──────────────────────────────────┐
│                     FastAPI (API Layer)                      │
│    Routes → Dependencies (auth, RBAC, pagination, audit)    │
├─────────────────────────────────────────────────────────────┤
│                    Service Layer                             │
│   Business logic, incident lifecycle, notification fanout   │
├─────────────────────────────────────────────────────────────┤
│                  Repository Layer                            │
│          SQLAlchemy async queries, CRUD operations           │
├─────────────────────────────────────────────────────────────┤
│                   PostgreSQL + Redis                         │
│         (Data persistence)   (Celery broker/backend)        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Celery Workers & Beat                       │
│  Scheduled health checks • Notification delivery • Metrics  │
└─────────────────────────────────────────────────────────────┘
```

**Key patterns:**
- **Repository → Service → API** — Each layer has a single responsibility
- **Dependency injection** — FastAPI `Depends()` for auth, RBAC, pagination, audit context
- **Async throughout** — `asyncpg` driver, `async/await` in all DB operations
- **Soft deletes** — Monitors use `deleted_at` instead of hard deletes

> For detailed architecture documentation, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Project Structure

```
sentinel/
├── app/                          # Backend application
│   ├── api/                      # API routes (v1)
│   │   └── v1/
│   │       ├── endpoints/        # Route handlers (auth, workspaces, monitors, etc.)
│   │       └── router.py         # API router aggregation
│   ├── core/                     # Framework config & middleware
│   │   ├── config.py             # Pydantic settings (all env vars)
│   │   ├── celery_app.py         # Celery app & beat schedule
│   │   ├── logging.py            # Structured logging (text/JSON)
│   │   ├── security.py           # JWT creation & verification
│   │   ├── security_headers.py   # HSTS, CSP, X-Frame-Options middleware
│   │   ├── rate_limit.py         # Per-IP rate limiting middleware
│   │   ├── sentry.py             # Sentry SDK initialization
│   │   └── redis.py              # Redis client singleton
│   ├── db/                       # Database session & base model
│   ├── models/                   # SQLAlchemy ORM models
│   ├── repositories/             # Data access layer (async queries)
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/                 # Business logic layer
│   └── workers/                  # Celery task definitions
├── frontend/                     # Next.js frontend application
│   ├── src/
│   │   ├── app/                  # App Router pages & layouts
│   │   │   ├── login/            # Login page
│   │   │   ├── register/         # Registration page
│   │   │   └── workspaces/       # Workspace routes
│   │   │       └── [id]/         # Dynamic workspace pages
│   │   │           ├── monitors/ # Monitor list & detail
│   │   │           ├── incidents/
│   │   │           ├── alerts/
│   │   │           ├── notifications/
│   │   │           ├── audit-logs/
│   │   │           └── settings/
│   │   ├── components/           # Reusable UI components
│   │   └── lib/                  # API client, utilities, auth helpers
│   ├── package.json
│   └── next.config.ts
├── alembic/                      # Database migration scripts
├── tests/                        # Pytest test suite (17 test files)
├── docs/                         # Extended documentation
├── .github/workflows/ci.yml      # GitHub Actions CI pipeline
├── docker-compose.yml            # Local dev orchestration
├── Dockerfile                    # Multi-stage production image
├── render.yaml                   # Render deployment blueprint
├── requirements.txt              # Production Python dependencies
├── requirements-dev.txt          # Dev/test dependencies
├── pyproject.toml                # Ruff, mypy, coverage config
└── .env.example                  # Environment variable template
```

---

## Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 18+** and **npm**
- **PostgreSQL 16+**
- **Redis** (optional for local dev — set `CELERY_TASK_ALWAYS_EAGER=true` to skip)

### Backend Setup

```bash
# 1. Clone the repository
git clone https://github.com/sarangs1621/Sentinel.git
cd Sentinel

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your database credentials, secret key, etc.

# 5. Run database migrations
alembic upgrade head

# 6. Start the API server
uvicorn app.main:app --reload
```

The API will be available at **http://localhost:8000**.  
Interactive API docs at **http://localhost:8000/docs**.

### Frontend Setup

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Set up environment variables
cp .env.example .env.local
# Edit .env.local — set NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# 4. Start the development server
npm run dev
```

The frontend will be available at **http://localhost:3000**.

### Docker Compose (Full Stack)

Spin up the entire stack (Postgres, Redis, API, Celery worker, Celery beat) with one command:

```bash
cp .env.example .env     # adjust values as needed
docker compose up -d
```

The `api` container runs `alembic upgrade head` automatically on startup.

| Service | Port | Description |
|---|---|---|
| `api` | 8000 | FastAPI application |
| `db` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Redis 7 (Celery broker) |
| `worker` | — | Celery worker (executes health checks & notifications) |
| `beat` | — | Celery beat (dispatches scheduled tasks) |

### Local Postgres on Windows (No Docker)

If you're running PostgreSQL locally without Docker (e.g., a user-owned instance on a custom port):

```powershell
# Start Postgres on port 5433
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" `
  -D "C:\Users\saran\pgdata\sentinel" `
  -l "C:\Users\saran\pgdata\sentinel.log" `
  -o "-p 5433" start

# Stop Postgres
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" `
  -D "C:\Users\saran\pgdata\sentinel" stop
```

Make sure your `.env` has `DATABASE_URL` pointing to port `5433`:
```
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5433/sentinel
```

---

## Environment Variables

Copy `.env.example` to `.env` and adjust values. All variables are documented below:

### Application

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `production`, or `testing` |
| `PROJECT_NAME` | `Sentinel` | Application name (shown in API docs) |
| `API_V1_PREFIX` | `/api/v1` | API route prefix |
| `BACKEND_CORS_ORIGINS` | `[]` | JSON array of allowed CORS origins |

### Security & Authentication

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(required)* | JWT signing key — must be ≥32 characters in production. Generate with: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | *(required)* | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `TEST_DATABASE_URL` | — | Separate database for tests |
| `DB_POOL_SIZE` | `5` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Extra connections allowed beyond pool size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for a pooled connection |
| `DB_POOL_RECYCLE_SECONDS` | `1800` | Recycle stale connections |
| `DB_POOL_PRE_PING` | `true` | Test connections before use |

### Background Jobs

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for Celery |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | `true` = run tasks synchronously (no Redis needed) |
| `CHECK_DISPATCH_INTERVAL_SECONDS` | `10` | How often to dispatch health checks |
| `METRICS_AGGREGATION_INTERVAL_SECONDS` | `3600` | How often to run daily metric aggregation |

### Rate Limiting

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable rate limiting |
| `RATE_LIMIT_REQUESTS` | `100` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window duration |
| `AUTH_RATE_LIMIT_REQUESTS` | `5` | Max login/register attempts per window |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | `60` | Auth rate limit window |
| `MAX_LOGIN_FAILURES` | `5` | Failed logins before account lockout |
| `LOGIN_LOCKOUT_WINDOW_SECONDS` | `900` | Account lockout duration (15 min) |

### Logging & Monitoring

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `LOG_FORMAT` | `text` | `text` for console, `json` for structured logs |
| `SENTRY_DSN` | *(unset)* | Sentry DSN — leave unset to disable |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Fraction of requests to trace |

### Email Notifications (Resend API)

| Variable | Default | Description |
|---|---|---|
| `RESEND_API_KEY` | *(unset)* | Your Resend API Key |
| `EMAIL_FROM_ADDRESS` | `onboarding@resend.dev` | Email "From" address |

### Frontend

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | — | Backend API URL (e.g., `http://localhost:8000/api/v1`) |

---

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description of changes"

# Apply all pending migrations
alembic upgrade head

# Downgrade one revision
alembic downgrade -1
```

---

## API Reference

All endpoints are prefixed with `/api/v1`. Interactive docs available at `/docs`.

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Create a user account |
| POST | `/auth/login` | — | OAuth2 password login → access + refresh token |
| POST | `/auth/refresh` | — | Rotate refresh token for a new token pair |
| POST | `/auth/logout` | — | Revoke a refresh token |
| GET | `/users/me` | user | Current user profile |

### Workspaces & Members

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/workspaces` | user | Create a workspace (creator becomes owner) |
| GET | `/workspaces` | user | List user's workspaces |
| POST | `/workspaces/join` | user | Join via invite code |
| GET | `/workspaces/{id}` | member | Workspace detail |
| PATCH | `/workspaces/{id}` | admin/owner | Update workspace |
| DELETE | `/workspaces/{id}` | owner | Delete workspace |
| POST | `/workspaces/{id}/invite-code/regenerate` | admin/owner | Rotate invite code |
| GET | `/workspaces/{id}/members` | member | List members |
| PATCH | `/workspaces/{id}/members/{user_id}` | admin/owner | Change member role |
| DELETE | `/workspaces/{id}/members/{user_id}` | admin/owner | Remove a member |
| DELETE | `/workspaces/{id}/members/me` | member | Leave workspace |

### Monitors

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/workspaces/{id}/monitors` | member | Create a monitor (HTTP/TCP/PING) |
| GET | `/workspaces/{id}/monitors` | member | List active monitors |
| GET | `/workspaces/{id}/monitors/{monitor_id}` | member | Monitor detail |
| PATCH | `/workspaces/{id}/monitors/{monitor_id}` | admin/owner/creator | Update a monitor |
| DELETE | `/workspaces/{id}/monitors/{monitor_id}` | admin/owner/creator | Soft-delete a monitor |

**Validation rules:**
- HTTP monitors require an absolute `http(s)://` URL
- TCP monitors require `host:port` format
- PING monitors require a bare hostname or IP
- Duplicate type + target within a workspace is rejected (409)

### Health Checks & Incidents

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/workspaces/{id}/monitors/{monitor_id}/checks` | member | Record a health check result |
| GET | `/workspaces/{id}/monitors/{monitor_id}/checks` | member | List check history |
| GET | `/workspaces/{id}/incidents` | member | List workspace incidents |
| GET | `/workspaces/{id}/incidents/{incident_id}` | member | Incident detail |
| PATCH | `/workspaces/{id}/incidents/{incident_id}` | admin/owner | Acknowledge or resolve an incident |

**Incident lifecycle:**
- Each monitor has a configurable `failure_threshold` (default: 3)
- Consecutive failures hitting the threshold → incident opened (severity: `major`, status: `open`)
- A successful check resets the counter and auto-resolves any open incident
- Admins/owners can manually acknowledge (`investigating`) or resolve incidents

### Alert Rules & Notifications

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/workspaces/{id}/alert-rules` | admin/owner | Create an alert rule |
| GET | `/workspaces/{id}/alert-rules` | admin/owner | List alert rules |
| GET | `/workspaces/{id}/alert-rules/{rule_id}` | admin/owner | Alert rule detail |
| PATCH | `/workspaces/{id}/alert-rules/{rule_id}` | admin/owner | Update an alert rule |
| DELETE | `/workspaces/{id}/alert-rules/{rule_id}` | admin/owner | Delete an alert rule |
| GET | `/workspaces/{id}/notifications` | member | List notifications |
| GET | `/workspaces/{id}/notifications/{notification_id}` | member | Notification detail |

**Channel types:** `webhook` (JSON POST) and `email` (via Resend REST API)  
**Severity filter:** `min_severity` can be `minor`, `major`, or `critical`  
**Retry logic:** Up to 5 delivery attempts per notification

### Analytics & Metrics

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/workspaces/{id}/monitors/{monitor_id}/metrics/latency` | member | Latency stats (avg/min/max/p50/p95/p99) |
| GET | `/workspaces/{id}/monitors/{monitor_id}/metrics/uptime` | member | Uptime/SLA report (check-based + time-based) |
| GET | `/workspaces/{id}/monitors/{monitor_id}/metrics/snapshots` | member | Daily metric snapshots |
| GET | `/workspaces/{id}/dashboard` | member | Workspace-wide status overview |

`latency` and `uptime` accept optional `start`/`end` ISO-8601 query params (default: trailing 24h, max range: 90 days).

### Audit Logs

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/workspaces/{id}/audit-logs` | admin/owner | List all audit log entries |
| GET | `/workspaces/{id}/audit-logs/search` | admin/owner | Search/filter by user, action, entity, date range |
| GET | `/workspaces/{id}/audit-logs/{audit_log_id}` | admin/owner | Single audit log entry |

Each entry includes: `action`, `entity_type`, `entity_id`, `old_values`, `new_values` (JSON diffs), `ip_address`, `user_agent`, and `created_at`. Audit logs are immutable — `PATCH`/`DELETE` return 405.

### System Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Basic liveness check (`{"status": "ok"}`) |
| GET | `/health/ready` | Readiness check (verifies DB + Redis connectivity) |

---

## Frontend Pages

| Route | Description |
|---|---|
| `/login` | User login form |
| `/register` | User registration form |
| `/workspaces` | List all workspaces, create new, join via invite code |
| `/workspaces/[id]` | Workspace dashboard — monitor/incident status overview |
| `/workspaces/[id]/monitors` | Monitor list with create/edit modal |
| `/workspaces/[id]/monitors/[monitorId]` | Monitor detail — check history, latency/uptime metrics |
| `/workspaces/[id]/incidents` | Incident list with status indicators |
| `/workspaces/[id]/alerts` | Alert rule management (create/edit/delete) |
| `/workspaces/[id]/notifications` | Notification delivery log |
| `/workspaces/[id]/audit-logs` | Audit trail with search/filter |
| `/workspaces/[id]/settings` | Workspace settings, member management, invite code |

---

## Scheduler & Background Workers

Sentinel uses Celery for background tasks. Three scheduled jobs run on Celery beat:

| Job | Interval | Description |
|---|---|---|
| `dispatch-due-checks` | `CHECK_DISPATCH_INTERVAL_SECONDS` (10s) | Find monitors due for a check and dispatch worker tasks |
| `dispatch-pending-notifications` | `CHECK_DISPATCH_INTERVAL_SECONDS` (10s) | Retry pending/failed notification deliveries |
| `aggregate-daily-metrics` | `METRICS_AGGREGATION_INTERVAL_SECONDS` (3600s) | Compute and upsert daily metric snapshots |

### Running Workers

```bash
# Start the worker (executes tasks)
celery -A app.core.celery_app worker --loglevel=info

# Start the beat scheduler (dispatches tasks on schedule)
celery -A app.core.celery_app beat --loglevel=info
```

Both require Redis. For local dev without Redis, set `CELERY_TASK_ALWAYS_EAGER=true` in `.env` to run tasks synchronously in-process.

### Local Polling Scheduler (No Redis Alternative)

For environments without Redis, `run_local_scheduler.py` provides a simple polling loop that dispatches checks and notifications synchronously:

```bash
python run_local_scheduler.py
```

---

## Testing

Tests run against a separate `TEST_DATABASE_URL` database.

```bash
# Create the test database
createdb sentinel_test   # or via psql/pgAdmin

# Run tests with coverage
pytest -v
```

### Coverage

Every `pytest` run reports line + branch coverage for `app/` and **fails if coverage drops below 95%**. The detailed HTML report is written to `htmlcov/index.html`.

```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html
```

The `concurrency = ["greenlet", "thread"]` setting in `pyproject.toml` ensures accurate coverage measurement across SQLAlchemy's async `greenlet_spawn` and Celery's threaded task execution.

---

## CI/CD

Every push and PR to `main` runs `.github/workflows/ci.yml` with five parallel jobs:

| Job | What It Checks |
|---|---|
| **Lint (ruff)** | `ruff check .` — code style & import ordering |
| **Type check (mypy)** | `mypy app` — static type analysis |
| **Test & coverage** | `pytest` against Postgres 16, gated at 95% coverage |
| **Docker build validation** | `docker build` + `docker compose config` validation |
| **Security checks** | `pip-audit` (dependency vulnerabilities) + `detect-secrets` (leaked secrets) |

### Updating the Secrets Baseline

If `detect-secrets` flags a false positive:

```bash
detect-secrets scan > .secrets.baseline
git add .secrets.baseline
git commit -m "chore: update secrets baseline"
```

---

## Deployment

### Backend — Render

The `render.yaml` Blueprint defines three services:

| Service | Type | Description |
|---|---|---|
| `sentinel-api` | Web service | FastAPI application with auto-migrations |
| `sentinel-worker` | Worker | Celery worker for health checks & notifications |
| `sentinel-beat` | Worker | Celery beat scheduler |

Plus managed Postgres (`sentinel-db`) and Redis (`sentinel-redis`).

**Deploy to Render:**
1. Push to GitHub
2. Connect your repo on [Render Dashboard](https://dashboard.render.com)
3. Render auto-detects `render.yaml` and provisions all services

### Frontend — Vercel

1. Import the `frontend/` directory on [Vercel](https://vercel.com)
2. Set the environment variable `NEXT_PUBLIC_API_URL` to your Render API URL
3. Vercel auto-deploys on every push to `main`

> For detailed deployment instructions, see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## Git Workflow & Branch Naming

Sentinel uses a **hybrid Git workflow** optimized for solo development:

### Rules

1. **`main` is always stable and deployable.** It is the single source of truth.
2. **Commit directly to `main`** for small, low-risk changes (typo fixes, styling tweaks, config adjustments, small helpers).
3. **Use a feature branch** for larger, multi-day features or major structural refactors. This ensures `main` always has a working version that can be deployed or demoed.

### Branch Naming Convention

All branches follow the format `<type>/<short-description>` with lowercase kebab-case:

| Prefix | Use Case | Example |
|---|---|---|
| `feature/` | New features or capabilities | `feature/slack-integration` |
| `fix/` | Bug fixes | `fix/token-refresh-loop` |
| `chore/` | Maintenance, dependencies, config | `chore/upgrade-fastapi` |
| `docs/` | Documentation only | `docs/api-reference-update` |
| `refactor/` | Code restructuring (no behavior change) | `refactor/service-layer-cleanup` |
| `test/` | Adding or updating tests only | `test/notification-edge-cases` |

### Workflow

```
main ─────────────────────────────────────────────────►
  │                                      │
  ├── feature/slack-integration ─────────┤  (merge when ready)
  │                                      │
  ├── small commit directly to main ─────┤
  │                                      │
  └── fix/token-refresh-loop ────────────┘  (merge when ready)
```

### Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>: <short description>

# Examples:
feat: add Slack notification channel
fix: prevent duplicate incidents for same monitor
chore: upgrade SQLAlchemy to 2.0.37
docs: update API reference with new endpoints
refactor: extract notification dispatcher to separate module
test: add edge case tests for uptime calculation
ci: add Node 22 to CI matrix
```

---

## Documentation

Extended documentation is available in the [`docs/`](docs/) directory:

| Document | Description |
|---|---|
| [`API.md`](docs/API.md) | Full API endpoint reference |
| [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture, patterns, and design decisions |
| [`DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Render + Vercel deployment guide |
| [`ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) | Entity-relationship diagram for all database models |
| [`FRONTEND.md`](docs/FRONTEND.md) | Frontend architecture, pages, and component structure |
| [`TESTING_MANUAL.md`](TESTING_MANUAL.md) | Manual testing procedures and scenarios |

---

<p align="center">
  Built by <a href="https://github.com/sarangs1621">sarangs1621</a>
</p>
