# dashboard.html — Pool Dashboard SPA

## What
Single-page HTML dashboard served by the FastAPI backend at `GET /dashboard`.
Displays real-time pool statistics (total, available, assigned, shared, leased,
suspended, credits), key listing, and SSE-powered live updates.

**Docs:** dashboard.html

## Why
- **Zero dependencies**: Pure HTML/CSS/JS, no build step, served as static file
- **SSE live updates**: `/api/v1/pool/events` stream for real-time key events
  (leased, returned, swapped) + periodic stats refresh every 30s
- **FastAPI auth integration**: Auth token injected server-side into the HTML

## Touched by
- `agent_toolbox/start_toolbox.py` — serves the HTML at `/dashboard`, injects auth token
- `agent_toolbox/api/routes/pool.py` — SSE stream at `/pool/events` + stats at `/pool/stats`

## Key features

### V19.14: assigned/shared stats
Two new stat cards ("Zugewiesen" / "Geteilt") showing soft-ownership metrics.
Colors: assigned = #6366f1 (purple-blue), shared = #f59e0b (orange).

### Live updates (SSE)
- `key_leased` → flash pool status bar, start countdown timer
- `key_returned` → flash pool status bar
- `key_swapped` → show swap notification (old alias → new alias)
- `stats` → update all stat cards (periodic 30s)

### Responsive grid
CSS Grid with `auto-fit minmax(200px, 1fr)` — flows from 2 to 7 columns
depending on viewport width.

## Usage
The dashboard is served at `http://localhost:8100/dashboard` when the backend
is running. Requires `SINATOR_AUTH_TOKEN` set for API access.

## Caveats
- Auth token is embedded server-side in the HTML (not secure for public internet)
- SSE reconnects on `EventSource` error with 5s backoff
- Pool status color thresholds: green >10, yellow 5-10, red <5 available keys
