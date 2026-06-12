# Frontend

The `frontend/` directory contains a Next.js (App Router) single-page
application that consumes the Sentinel REST API. It is a separate
deployable from the FastAPI backend — typically the frontend is hosted on
Vercel while the API, Postgres, Redis, and Celery workers run elsewhere
(Docker Compose, a VM, or a container platform), since Vercel does not run
long-lived processes like Postgres/Redis/Celery.

## Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router), React 19, TypeScript |
| Styling | Tailwind CSS v4 |
| Data fetching | TanStack React Query |
| Forms & validation | react-hook-form + zod |
| Charts | Recharts |

The app is intentionally client-rendered ("use client" pages backed by
React Query) — it talks to the FastAPI backend entirely over its public
REST API, with no server-side rendering or API routes of its own.

## Structure

```
frontend/src/
├── app/
│   ├── login/, register/          # auth pages (redirect if already signed in)
│   ├── workspaces/                 # workspace picker (list / create / join)
│   └── workspaces/[workspaceId]/   # workspace-scoped shell + nested routes
│       ├── layout.tsx              # fetches the workspace, renders the nav shell
│       ├── dashboard/              # stats, monitor-status chart, open incidents
│       ├── monitors/               # list, create, detail (checks/metrics/charts)
│       └── incidents/              # list (filterable), detail (acknowledge/resolve)
├── components/
│   ├── ui/                         # hand-built Tailwind primitives (Button, Card, Badge, ...)
│   ├── AuthGuard.tsx                # client-side redirect to /login when signed out
│   └── layout/WorkspaceShell.tsx    # top nav + sidebar for workspace routes
└── lib/
    ├── api.ts                      # typed fetch client (Bearer auth, refresh-on-401)
    ├── auth-context.tsx             # AuthProvider / useAuth
    ├── workspace-context.tsx        # current workspace + role, via useWorkspace
    ├── types.ts                     # TypeScript types mirroring the Pydantic schemas
    └── providers.tsx                # QueryClientProvider + AuthProvider
```

## Authentication model

The API issues JWT access + refresh tokens via the OAuth2 password flow
(`POST /auth/login`, `username` = email). The frontend stores both tokens in
`localStorage` and:

- attaches `Authorization: Bearer <access_token>` to every request,
- on a `401`, transparently calls `POST /auth/refresh` once and retries the
  original request,
- if the refresh also fails, clears tokens and redirects to `/login`.

`WorkspaceRead.role` returns the *requesting user's* role directly, so the
UI can gate admin/owner-only actions (editing alert rules, regenerating
invite codes, acknowledging/resolving incidents, removing other members'
monitors) without a separate members lookup.

## Local development

```bash
cd frontend
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL if not using the default
npm install
npm run dev
```

The app runs at http://localhost:3000 and expects the API at
`NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api/v1` — see the
[root Local Setup](../README.md#local-setup) to run the backend via Docker
Compose).

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Base URL of the Sentinel API, **including** the `/api/v1` prefix. Exposed to the browser (`NEXT_PUBLIC_*`), so it must point at a publicly reachable API origin in production. |

## Deploying to Vercel

1. Push this repo to GitHub (already done) and import it into Vercel.
2. Set the project's **Root Directory** to `frontend/`. Vercel auto-detects
   Next.js and configures the build (`npm run build`) and output with no
   further config.
3. Add the `NEXT_PUBLIC_API_URL` environment variable in the Vercel project
   settings, pointing at your deployed backend, e.g.
   `https://api.yourdomain.com/api/v1`.
4. Deploy. Every push to `main` (and PR previews) builds automatically.

### Backend CORS configuration

Once the frontend has a Vercel URL (e.g.
`https://sentinel-frontend.vercel.app`, plus any preview-deployment
domains you use), add it to the backend's `BACKEND_CORS_ORIGINS`
environment variable — see
[`docs/DEPLOYMENT.md`](DEPLOYMENT.md#environment-variables). This is a
comma-separated list (or JSON array) of explicit origins; wildcards
(`*`) are rejected at startup:

```
BACKEND_CORS_ORIGINS=https://sentinel-frontend.vercel.app,http://localhost:3000
```

Without this, the browser will block requests from the deployed frontend
with a CORS error even though the API itself responds successfully (see
the CORS rows in [`docs/DEPLOYMENT.md`](DEPLOYMENT.md#troubleshooting)).
