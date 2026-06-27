# Frontend

The Sentinel frontend is a [Next.js 15](https://nextjs.org/) (App Router) +
[React 19](https://react.dev/) + TypeScript single-page application located in
[`frontend/`](../frontend). It is a thin client over the FastAPI backend: all
state lives on the server, and the frontend is a typed REST client with a
custom dark-themed UI.

## Stack

| Layer       | Choice                                                            |
| ----------- | ------------------------------------------------------------------ |
| Framework   | Next.js 15 (App Router, `output: "standalone"`)                  |
| UI library  | React 19                                                          |
| Language    | TypeScript 5.7                                                    |
| Styling     | Hand-written CSS design system (`src/app/globals.css`) — no Tailwind/CSS framework |
| Data access | Plain `fetch` wrapper (`src/lib/api.ts`) — no React Query/SWR     |
| Auth        | JWT access + refresh tokens stored in `localStorage`              |
| Charts      | Inline SVG/canvas in page components — no charting library        |

No Tailwind CSS, React Query, Zod, react-hook-form, or Recharts are used. The
goal was a small, dependency-light bundle with a single shared stylesheet.

## Project structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout, global metadata/viewport
│   │   ├── globals.css         # Design system (glass-card, btn, badge, etc.)
│   │   ├── page.tsx             # "/" — redirects to /workspaces or /login
│   │   ├── icon.svg             # Favicon
│   │   ├── not-found.tsx        # Custom 404
│   │   ├── error.tsx            # Client error boundary
│   │   ├── login/page.tsx       # "/login"
│   │   ├── register/page.tsx    # "/register"
│   │   └── workspaces/
│   │       ├── layout.tsx       # Auth guard + sidebar/app shell
│   │       ├── page.tsx         # "/workspaces" — list/create/join workspaces
│   │       └── [id]/
│   │           ├── page.tsx               # Dashboard (metrics, status overview)
│   │           ├── monitors/
│   │           │   ├── page.tsx           # Monitor list + create/edit modal
│   │           │   └── [monitorId]/page.tsx  # Monitor detail (checks, metrics, incidents)
│   │           ├── incidents/page.tsx     # Incident list + detail/resolve
│   │           ├── alerts/page.tsx        # Alert rule management
│   │           ├── notifications/page.tsx # Notification delivery log
│   │           ├── audit-logs/page.tsx    # Workspace audit log
│   │           └── settings/page.tsx      # General / Members / API Keys tabs
│   ├── components/
│   │   └── MonitorModal.tsx     # Create/edit monitor form (modal)
│   └── lib/
│       ├── api.ts                # Typed fetch client + all DTOs
│       └── utils.ts              # Formatting helpers (dates, durations, badges)
├── next.config.ts
├── tsconfig.json
├── .env.example
└── .gitignore
```

Routes use the dynamic segment `[id]` for the workspace ID (not
`[workspaceId]`), matched against `useParams()` in `workspaces/layout.tsx`.

## Authentication model

There is no React context/provider for auth. Each protected layout/page:

1. Reads `access_token` from `localStorage` on mount.
2. If missing, redirects to `/login` via `router.replace`.
3. Otherwise calls `apiGetMe()` to fetch the current user and render the page.

`src/lib/api.ts` exports `setTokens`, `clearTokens`, and an `apiFetch<T>`
wrapper that:

- Attaches `Authorization: Bearer <access_token>` to every request.
- On a `401` response, calls `/auth/refresh` with the stored refresh token,
  retries the original request once, and otherwise clears tokens and
  redirects to `/login`.
- Normalizes FastAPI's `{"detail": ...}` error bodies (string or pydantic
  validation array) into a single `ApiError` with a human-readable message.

## Design system

All shared styles live in `src/app/globals.css`. Key building blocks:

- **Layout**: `.auth-page` / `.auth-card` (login/register/404/error), `.app-layout` / `.sidebar` / `.main-content` (authenticated shell)
- **Cards & grids**: `.glass-card`, `.metrics-grid`, `.workspace-grid`
- **Forms**: `.input-field`, `.select-field`, `.btn` / `.btn-primary` / `.btn-secondary` / `.btn-ghost` / `.btn-danger`
- **Status badges**: `.badge` plus variants — `badge-up`, `badge-down`, `badge-pending`, `badge-success`, `badge-failure`, `badge-open`, `badge-investigating`, `badge-resolved`, `badge-critical`, `badge-major`, `badge-minor`, `badge-neutral`
- **Modals**: `.modal-overlay` / `.modal-content`
- **Misc**: `.tabs` / `.tab`, `.empty-state`, `.skeleton`, `.stagger-children`, `.loading-page`

The accent color is a purple/indigo gradient
(`--accent-gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%)`)
on a near-black background (`--bg-primary: #0a0e1a`).

## Environment variables

| Variable               | Description                                          | Default (`.env.example`)              |
| ----------------------- | ----------------------------------------------------- | ---------------------------------------- |
| `NEXT_PUBLIC_API_URL`  | Base URL of the Sentinel API, including `/api/v1`     | `http://localhost:8000/api/v1`         |

Copy `frontend/.env.example` to `frontend/.env.local` and adjust for your
environment. `.env.local` is gitignored.

## Local development

```bash
cd frontend
cp .env.example .env.local   # adjust NEXT_PUBLIC_API_URL if needed
npm install
npm run dev
```

The app runs at `http://localhost:3000` and expects the backend (see the
[root README](../README.md)) running at the URL configured in
`NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), with
`BACKEND_CORS_ORIGINS` including `http://localhost:3000`.

## Production build & deployment

```bash
npm run build
npm start
```

`next.config.ts` sets `output: "standalone"` for containerized deployments.
For a Vercel deployment, set `NEXT_PUBLIC_API_URL` to the deployed backend's
URL (e.g. a Render service, see [`render.yaml`](../render.yaml)) and ensure
the backend's `BACKEND_CORS_ORIGINS` includes the Vercel deployment URL.
