# Sentinel — Manual Testing Guide

This guide walks through every user-facing feature of Sentinel (frontend +
backend together) so you can manually verify the app is complete and
production-ready. Check items off as you go.

---

## 0. Prerequisites

Both servers should already be running:

| Service  | URL                              | Check |
|----------|----------------------------------|-------|
| Backend  | http://localhost:8000             | `GET /health` → `{"status":"ok"}` |
| Frontend | http://localhost:3000             | Loads the Sentinel UI |
| Swagger  | http://localhost:8000/docs        | Interactive API docs (for "API-only" items below) |

If either isn't running:

```bash
# Backend (from project root, venv active)
.venv/Scripts/python.exe -m uvicorn app.main:app --reload

# Frontend
cd frontend
npm run dev
```

Notes on local config:
- `.env`: `CELERY_TASK_ALWAYS_EAGER=true` — alert notifications/incident
  detection run synchronously in the request, so you don't need
  Redis/Celery running locally to see incidents/notifications appear.
- `frontend/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`
- Postgres dev DB on port 5433.

---

## 1. Authentication

### 1.1 Landing redirect
- [ ] Visit `http://localhost:3000/` with no token in `localStorage` →
      redirects to `/login`.
- [ ] After logging in, visiting `/` redirects straight to `/workspaces`.

### 1.2 Register (`/register`)
- [ ] Fields: **Full name** (optional), **Email** (required), **Password**
      (required, placeholder "Min 8 chars, with a letter and digit").
- [ ] Try a password under 8 characters → browser-native validation blocks
      submission (HTML `minLength=8`).
- [ ] Try a password ≥8 chars but missing a digit or letter (e.g.
      `"passwordonly"`) → backend rejects with a validation error shown in
      the red error banner above the form (message should be the cleaned-up
      `Value error, ...` text from the API, e.g. "Password must contain at
      least one digit").
- [ ] Register with a brand-new email + valid password (e.g.
      `tester@example.com` / `Passw0rd1`) → button shows "Creating account…"
      then redirects to `/workspaces` (you're auto-logged-in).
- [ ] Register again with the **same email** → error banner shows
      "already registered" (or similar) message.
- [ ] "Already have an account? **Sign in**" link → `/login`.

### 1.3 Login (`/login`)
- [ ] Fields: Email, Password.
- [ ] Wrong password → red error banner with message, form stays usable.
- [ ] Correct credentials → "Signing in…" then redirect to `/workspaces`.
- [ ] "Don't have an account? **Create one**" link → `/register`.

### 1.4 Session / token handling
- [ ] After login, open DevTools → Application → Local Storage → confirm
      `access_token` and `refresh_token` are set.
- [ ] **Token refresh**: in DevTools, edit `access_token` to an invalid
      string (keep `refresh_token` intact), then navigate to any workspace
      page → the app should transparently refresh the token (one failed
      request retried) and the page loads normally, with a new
      `access_token` written back to storage.
- [ ] **Full logout**: clear both tokens (or use the sign-out flow below),
      then visit a workspace URL directly → redirected to `/login`.

### 1.5 Logout
- [ ] Click the user avatar/name block at the bottom of the sidebar
      (tooltip "Sign out") → calls logout and redirects to `/login`.
- [ ] After logout, the back button / direct URL to a previous workspace
      page redirects to `/login` (no stale data flashes).

### 1.6 API-only auth endpoints (Swagger)
These have no dedicated UI button — verify via `http://localhost:8000/docs`:
- [ ] `POST /api/v1/auth/refresh` — exchange refresh token for new access
      token.
- [ ] `POST /api/v1/auth/logout-all` — revokes **all** refresh tokens for
      the user (useful as a "sign out everywhere" security action).

---

## 2. Workspaces (`/workspaces`)

### 2.1 Empty state
- [ ] Brand-new account with no workspaces shows: 🏢 **No workspaces yet**,
      with "Create your first workspace... or join an existing one with an
      invite code." and a "+ Create workspace" button.

### 2.2 Create workspace
- [ ] Click "**+ Create workspace**" → modal with **Name*** (required),
      **Slug** (optional, e.g. auto-generated if blank), **Description**
      (optional textarea).
- [ ] Submit with only Name filled → "Creating…" then redirects to the new
      workspace's dashboard (`/workspaces/{id}`).
- [ ] Create a second workspace with a custom slug to confirm the slug is
      respected (check the invite-code / settings page or the workspace
      card's `/slug` line).

### 2.3 Join workspace via invite code
- [ ] From the workspace list, click "**Join workspace**" → modal with
      **Invite code*** field (placeholder "Paste invite code here").
- [ ] Get a real invite code from Settings → General of an existing
      workspace (see §10.1), paste it, submit → redirects to that
      workspace's dashboard.
- [ ] Submit a garbage code → error shown inside the modal (e.g. "Invalid
      invite code").

### 2.4 Workspace grid
- [ ] Each card shows: first-letter avatar, workspace name, `/slug`,
      description (if set), a role badge (`owner`/`admin`/`member`), and
      "Created X ago".
- [ ] Clicking a card navigates to that workspace's dashboard.

---

## 3. Sidebar / Navigation
- [ ] Sidebar always shows the "S Sentinel" logo and a "🏢 Workspaces" link.
- [ ] Inside a workspace, a section label shows the **workspace name**,
      followed by: 📊 Dashboard, 🖥️ Monitors, 🔔 Incidents, ⚡ Alert Rules,
      📨 Notifications, 📋 Audit Log, ⚙️ Settings.
- [ ] The active page's nav link is visually highlighted.
- [ ] Resize the browser to a narrow/mobile width → sidebar collapses,
      hamburger (☰) button appears top-left; clicking it slides the sidebar
      in with a backdrop; clicking the backdrop or a link closes it.
- [ ] Sidebar footer shows your avatar (initials), name, email — clicking it
      signs you out.

---

## 4. Dashboard (`/workspaces/[id]`)

Use a workspace with at least one monitor for this section (create one in
§5 first, then come back).

- [ ] Title "Dashboard", subtitle "Last 24 hours overview · N monitors".
- [ ] Four metric cards:
  - [ ] 📡 **Total Monitors** — total count + "X up · Y down · Z pending"
        breakdown.
  - [ ] ✅ **Check Pass Rate** — percentage (green if ≥99%), with "N checks
        in period" subtitle.
  - [ ] ⚡ **Avg Response Time** — formatted ms/s across all monitors.
  - [ ] 🔔 **Active Incidents** — count (red if >0, green if 0), with
        "X open · Y investigating" subtitle.
- [ ] **Monitors table**: Name / Type / Status / Response / Last Check.
      Clicking a row navigates to that monitor's detail page.
- [ ] If there are **no monitors**: empty state "🖥️ No monitors yet" with a
      "+ Add monitor" button that navigates to the Monitors page.
- [ ] **Active Incidents** section appears only when there's at least one
      non-resolved incident, listing up to 5 (title, "Created X ago",
      severity + status badges); clicking one navigates to the Incidents
      page.

---

## 5. Monitors

### 5.1 List (`/workspaces/[id]/monitors`)
- [ ] Title "Monitors", subtitle "{N} monitors configured".
- [ ] "+ New monitor" button opens the create modal.
- [ ] Empty state: 🖥️ **No monitors yet** with "+ New monitor" button.
- [ ] Each row shows: type icon, name, target (monospace, truncated),
      status badge with colored dot, "⏸ Paused" badge if inactive, last
      checked time (relative, or "—" if never), and action buttons
      ⏸/▶ (pause/resume), ✏️ (edit), 🗑 (delete).
- [ ] Clicking anywhere on a row (not a button) navigates to the monitor
      detail page.

### 5.2 Create a monitor
- [ ] Open "+ New monitor". Fields:
  - **Name*** (placeholder "Production API")
  - **Type*** — select 🌐 HTTP / 🔌 TCP / 📡 PING (target placeholder
    changes accordingly: `https://example.com/health`, `db.example.com:5432`,
    `1.1.1.1`)
  - **Target*** (required)
  - **Check interval (s)** — number, min 30, max 86400, default 60
  - **Failure threshold** — number, min 1, max 100, default 3
- [ ] Try submitting with interval < 30 or > 86400 → browser blocks via
      `min`/`max` constraints.
- [ ] Create one of each type for thorough testing:
  - HTTP: target `https://httpstat.us/200` (should go **up**)
  - HTTP (failing): target `https://httpstat.us/500` with
    `failure_threshold = 1`, `check_interval_seconds = 30` (should go
    **down** quickly and create an incident — see §6)
  - TCP: target `1.1.1.1:443` (should go **up**)
  - PING: target `1.1.1.1` (should go **up**, or **down** if ICMP is
    blocked in your environment — note this is expected on some networks)
- [ ] After creating, modal closes and the new monitor appears in the list
      with status `pending` until the first check runs.

### 5.3 Trigger a check manually (API-only)
The UI has no "run check now" button — checks run on the scheduler
(`run_local_scheduler.py`) or via Celery beat. To force an immediate check
for testing:
- [ ] Via Swagger (`/docs`), call
      `POST /api/v1/workspaces/{workspace_id}/monitors/{monitor_id}/checks`
      — confirm it returns a check result and the monitor's `status` /
      `last_checked_at` update on refresh.
- [ ] Alternatively, run `run_local_scheduler.py` in a separate terminal to
      have it poll all active monitors automatically.

### 5.4 Edit a monitor
- [ ] Click ✏️ on a monitor → modal opens pre-filled. The **Type** field is
      now a disabled, read-only display (icon + uppercase type) — confirm
      it cannot be changed.
- [ ] An extra checkbox appears: "**Monitor active (uncheck to pause
      checks)**".
- [ ] Change the name and/or interval, click "Save changes" → "Saving…"
      then list refreshes with new values.

### 5.5 Pause / Resume
- [ ] Click ⏸ on an active monitor → becomes paused, "⏸ Paused" badge
      appears, button changes to ▶, row dims slightly.
- [ ] Click ▶ to resume → badge disappears, row returns to full opacity.
- [ ] Confirm pausing a monitor stops it from being checked (status stops
      updating).

### 5.6 Delete a monitor
- [ ] Click 🗑 → native confirm dialog: "Delete this monitor? This action
      cannot be undone." → Cancel keeps it; OK removes it from the list.

### 5.7 Monitor detail page (`/workspaces/[id]/monitors/[monitorId]`)
- [ ] "← Back" button returns to the monitors list.
- [ ] Header shows type icon + name + status badge + (if paused) "⏸ Paused"
      badge + monospace target.
- [ ] "Pause"/"Resume" and "Edit" buttons work the same as on the list.
- [ ] Four metric cards:
  - [ ] ✅ **Uptime %** with "successful/total checks" subtitle
  - [ ] ⚡ **Avg Latency** with p95/p99 subtitle
  - [ ] 📊 **Response Range** (min → max)
  - [ ] 🔔 **Incidents** count + total downtime in minutes
- [ ] **Latency chart** (canvas): plots the last 50 checks with response
      times as a gradient-filled line; dots are green for successful checks
      and red for failures; Y-axis shows ms gridlines/labels.
  - [ ] If the monitor has no checks with response times yet, shows
        "No check data available yet" instead of the chart.
  - [ ] Resize the browser window → chart redraws to fit the new width.
- [ ] **Recent Checks** table (last 20): Status badge / Response Time /
      Error (or "—") / Time.
  - [ ] If no checks yet: "No checks recorded yet".
- [ ] **Incident History** section appears only if this monitor has
      associated incidents, showing title, "Created X ago", severity +
      status badges.

---

## 6. Incidents (`/workspaces/[id]/incidents`)

To generate a real incident: create an HTTP monitor pointing at a URL that
returns an error (e.g. `https://httpstat.us/500`) with
`failure_threshold = 1`, then trigger a check (manually via Swagger, or let
the scheduler run). The failing check should auto-create an incident.

- [ ] Subtitle reads "{open + investigating} active incidents".
- [ ] Filter tabs: **All / Open / Investigating / Resolved**, each showing a
      live count badge.
- [ ] Each incident card shows: title, "Created X ago" (+ "Resolved
      <date/time>" once resolved), severity badge (minor/major/critical),
      status badge with dot (open/investigating/resolved).
- [ ] For an **open** incident: "🔍 Acknowledge" and "✓ Resolve" buttons are
      both visible.
  - [ ] Click "🔍 Acknowledge" → status changes to **investigating**, the
        "Acknowledge" button disappears, "✓ Resolve" remains.
- [ ] For an **investigating** incident: only "✓ Resolve" is shown.
  - [ ] Click "✓ Resolve" → status becomes **resolved**, both action
        buttons disappear, "Resolved <date>" appears in the meta line.
- [ ] Switch filter tabs to confirm counts and filtering work correctly
      (e.g. a resolved incident only appears under "All" and "Resolved").
- [ ] Empty states:
  - [ ] "All" filter with zero incidents: 🎉 **No incidents** / "All systems
        are operating normally."
  - [ ] Other filters with zero matches: "No {filter} incidents" / "No
        incidents match this filter."
- [ ] Resolve the failing monitor's underlying issue (e.g. edit it back to a
      healthy target) and confirm a new check resolves/avoids new
      incidents.

---

## 7. Alert Rules (`/workspaces/[id]/alerts`)

- [ ] "+ New alert rule" → modal:
  - **Name*** (placeholder "Slack production alerts")
  - **Channel type*** — 🔗 Webhook / 📧 Email (target placeholder changes:
    `https://hooks.slack.com/services/...` vs `alerts@example.com`)
  - **Target*** (required)
  - **Minimum severity** — Any severity (default) / Minor / Major /
    Critical
- [ ] Create a **webhook** rule with "Any severity" — target it at a test
      endpoint (e.g. https://webhook.site URL) so you can confirm delivery
      later in §8.
- [ ] Create an **email** rule with minimum severity = Major.
- [ ] List shows for each rule: channel icon, name, target (monospace,
      truncated), "{≥severity or All severities} · {relative created
      time}".
- [ ] Click "**Disable**" on an enabled rule → row dims, button becomes
      "**Enable**". Click again to re-enable.
- [ ] Click 🗑 → confirm "Delete this alert rule?" → Cancel keeps it, OK
      removes it.
- [ ] Empty state: ⚡ **No alert rules**, with description and a "+ New
      alert rule" button.
- [ ] Trigger a new incident (per §6) and confirm matching enabled alert
      rules produce entries in the Notifications log (§8).

---

## 8. Notifications (`/workspaces/[id]/notifications`)

- [ ] Subtitle "Alert delivery log for this workspace".
- [ ] Filter dropdown: All statuses / Sent / Failed / Pending.
- [ ] Table columns: Time, Event (e.g. "Incident opened" / "Incident
      resolved"), Incident (title if resolvable, else id prefix), Channel
      (icon + rule name, or id prefix if rule was deleted), Status badge,
      Attempts, Response (HTTP status code or "—"), Error (message or "—").
- [ ] After an incident fires with a webhook alert rule pointed at
      webhook.site, confirm:
  - [ ] A row appears with event "Incident opened", correct channel/rule
        name, and status `sent` (or `failed` if the endpoint is
        unreachable — check the Error column for details).
  - [ ] When the incident is resolved (§6), a second row appears with event
        "Incident resolved".
- [ ] Filter by "Failed" / "Sent" / "Pending" and confirm only matching rows
      show.
- [ ] Empty state: 📨 **No notifications yet**.

---

## 9. Audit Logs (`/workspaces/[id]/audit-logs`)

- [ ] Action and Entity-type filter dropdowns are populated dynamically
      from the currently-loaded log entries (this is by design — combining
      filters narrows the available options progressively, so if you pick
      an action first, the entity-type list may shrink to only types seen
      for that action).
- [ ] Table columns: Time, Action (badge), Entity, User (first 8 chars of
      user id, or "system" for automated actions), Changes (JSON diff,
      truncated), IP address.
- [ ] Perform a variety of actions in other pages and confirm corresponding
      audit entries appear, e.g.:
  - [ ] Creating/updating/deleting a monitor → `monitor.created` /
        `monitor.updated` / `monitor.deleted`
  - [ ] Creating/deleting an alert rule → `alert_rule.created` /
        `alert_rule.deleted`
  - [ ] Acknowledging/resolving an incident → `incident.acknowledged` /
        `incident.resolved`
  - [ ] Creating/revoking an API key → `api_key.created` / `api_key.revoked`
  - [ ] Updating workspace settings → `workspace.updated`
  - [ ] Adding/removing a member → `member.added` / `member.removed`
- [ ] Empty state: 📋 **No audit log entries**.
- [ ] API-only: `GET /api/v1/workspaces/{id}/audit-logs/search` supports
      additional query params not exposed in the UI — try it in Swagger.

---

## 10. Settings (`/workspaces/[id]/settings`)

### 10.1 General tab
- [ ] **Workspace details** form: Name + Description.
  - [ ] As **owner/admin**: fields are editable, "Save changes" button
        present. Edit and save → green success banner "Workspace updated
        successfully".
  - [ ] As **member** (use a second account joined via invite code): fields
        are disabled, no save button.
- [ ] **Invite code** card:
  - [ ] Clicking the code copies it to clipboard and shows green "Copied!"
        banner.
  - [ ] As owner/admin: "Regenerate" button → confirm "Regenerate invite
        code? The old code will stop working." → OK generates a new code
        and shows "Invite code regenerated".
  - [ ] As member: no "Regenerate" button.
- [ ] **Danger zone**:
  - [ ] As **owner**: "Delete workspace" button → confirm "Delete this
        workspace? This action is permanent and cannot be undone." → OK
        deletes the workspace and redirects to `/workspaces`.
        ⚠️ **Do this last** in your testing, on a throwaway workspace.
  - [ ] As **non-owner** (admin or member): "Leave workspace" button →
        confirm "Leave this workspace? You will lose access unless
        re-invited." → OK removes you and redirects to `/workspaces`.

### 10.2 Members tab
- [ ] Tab label shows member count, e.g. "Members 2".
- [ ] Table: Member (avatar + name + email), Role, Joined, Actions.
- [ ] As owner/admin, for non-owner rows: Role is a `<select>` (member ↔
      admin) — change it and confirm it persists on reload.
- [ ] Owner's own row: role shown as a static badge, not editable.
- [ ] "Remove" button (not shown for the owner row) → confirm "Remove this
      member from the workspace?" → removes them from the members table.
- [ ] As a plain **member**: no Actions column at all (read-only table).

### 10.3 API Keys tab
- [ ] Tab is **only visible to owner/admin** — confirm it's hidden entirely
      for member-role users.
- [ ] **Create API key**: enter a Name (required), click "+ Create key" →
      a one-time secret banner appears with the full key value.
  - [ ] Click the key to copy it (shows "Copied!" banner).
  - [ ] Click "Done" → banner disappears (and the key is never shown again
        — confirm only the prefix shows in the table afterwards).
- [ ] Table columns: Name, Key (`prefix…`), Created, Last used (relative
      time or "Never"), Status (`Active` / `Revoked` badge), Actions.
- [ ] Click "Revoke" on an active key → confirm "Revoke this API key? Any
      integration using it will stop working immediately." → OK changes
      status to `Revoked` and removes the Revoke button.
- [ ] Empty state: 🔑 **No API keys**.
- [ ] (Optional, API-only) Use the created key as a Bearer token against a
      protected endpoint in Swagger to confirm it authenticates correctly,
      then confirm a revoked key returns 401.

---

## 11. UI/UX & Edge Cases

- [ ] **404 page**: visit a nonexistent route (e.g.
      `/workspaces/does-not-exist/foo`) → branded 404 page with gradient
      "404", "Page not found" message, and "Go home" button → `/`.
- [ ] **Error boundary**: if a page throws a render error, the branded
      "⚠️ Something went wrong" screen appears with "Try again" (resets) and
      "Go home" buttons (hard to trigger manually — spot-check that the
      component exists and renders correctly if you can force an error).
- [ ] **Page titles**: browser tab title follows "{Page} · Sentinel" pattern
      (check via document title on a few pages) and the root metadata
      description/keywords are set (view page source or DevTools
      `<head>`).
- [ ] **Favicon**: confirm the Sentinel "S" icon shows in the browser tab.
- [ ] **Loading states**: hard-refresh various pages and confirm skeleton
      placeholders show briefly instead of layout jumps.
- [ ] **Responsive layout**: test at desktop, tablet, and mobile widths —
      sidebar collapses correctly, tables remain usable (horizontal scroll
      via `.table-wrapper` if needed), modals stay centered and scrollable
      on small screens.
- [ ] **Empty states**: confirm every list page (Workspaces, Monitors,
      Incidents, Alert Rules, Notifications, Audit Logs, API Keys) shows a
      sensible icon + title + description when empty, as covered in each
      section above.

---

## 12. Multi-user / permissions smoke test

Using two browser profiles (or one normal + one incognito window) with two
different accounts:

- [ ] User A creates a workspace (becomes `owner`).
- [ ] User A copies the invite code from Settings → General.
- [ ] User B registers/logs in and joins via that invite code (becomes
      `member`).
- [ ] Confirm User B sees the workspace in their list, can view
      Dashboard/Monitors/Incidents/Alerts/Notifications/Audit Log, but:
  - [ ] Cannot edit workspace name/description (fields disabled).
  - [ ] Cannot regenerate invite code.
  - [ ] Does not see the API Keys tab.
  - [ ] Sees "Leave workspace" (not "Delete workspace") in Danger Zone.
  - [ ] In Members tab, sees a read-only table (no role selects / Remove
        buttons).
- [ ] User A promotes User B to `admin` via Members tab → User B reloads
      and now sees the API Keys tab and editable workspace fields.

---

## 13. Backend API checks (Swagger — `http://localhost:8000/docs`)

Spot-check these endpoints that have no dedicated UI:
- [ ] `POST /api/v1/auth/logout-all`
- [ ] `POST /api/v1/workspaces/{workspace_id}/monitors/{monitor_id}/checks`
      (manual check trigger)
- [ ] `GET /api/v1/workspaces/{workspace_id}/audit-logs/search`
- [ ] `GET /api/v1/workspaces/{workspace_id}/monitors/{monitor_id}/metrics/*`
      (latency/uptime/snapshots — backs the dashboard & monitor detail
      charts)

---

## 14. Project / deployment status

- All 4 PRs are pushed and open on GitHub, ready for review/merge:
  - **#1** `docs/phase-13-portfolio-readiness` → `main` (docs)
  - **#2** `feature/frontend-app` → #1 (complete new frontend)
  - **#3** `fix/readiness-check-and-secret-placeholder` → `main`
  - **#4** `chore/production-readiness-hardening` → #3 (Render config +
    local scheduler + `.gitignore`/`.env.example` hardening)
- `render.yaml` (repo root) defines the API/worker/beat/Postgres services
  for deploying the backend to Render.
- The frontend (`frontend/`) is a separate deployable, intended for Vercel —
  see `docs/FRONTEND.md` on PR #2 for environment variables (just
  `NEXT_PUBLIC_API_URL`) and CORS setup notes (`BACKEND_CORS_ORIGINS` on the
  backend must include the deployed frontend origin).

---

### Quick reference: confirm dialogs you'll encounter
| Action | Confirm text |
|---|---|
| Delete monitor | "Delete this monitor? This action cannot be undone." |
| Delete alert rule | "Delete this alert rule?" |
| Regenerate invite code | "Regenerate invite code? The old code will stop working." |
| Delete workspace | "Delete this workspace? This action is permanent and cannot be undone." |
| Leave workspace | "Leave this workspace? You will lose access unless re-invited." |
| Remove member | "Remove this member from the workspace?" |
| Revoke API key | "Revoke this API key? Any integration using it will stop working immediately." |

Happy testing! Anything that doesn't match this guide is either a bug or a
spec drift worth flagging.
