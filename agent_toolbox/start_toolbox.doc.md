# start_toolbox.py — SINator FastAPI App Entry

## What
FastAPI application entry point for the SINator Agent Toolbox backend. Hosts all
API routes (GMX, Fireworks, Pool, Rotation, Config) and runs background tasks.

## Why
Single-process backend that ties together:
- Pool management (leasing, returning, stats)
- Browser automation services (GMX, Fireworks)
- Rotation orchestration
- Dashboard SPA serving

## Touched by
- `com.sinator.backend` (LaunchAgent) — starts the app via uvicorn
- All API route modules in `agent_toolbox/api/routes/`
- Frontend dashboard via REST/SSE

## Background tasks

### V19.10: Lease cleanup loop
Runs `expire_leases()` every 60 seconds. Cleans up stale leases from crashed
proxies that didn't call `/pool/return`. Started in `lifespan()` async context
manager as an asyncio task. Cancelled on shutdown.

## Auth
Token via `SINATOR_AUTH_TOKEN` env var. Auto-generated if not set (logged once
at startup, NOT persistent across restarts — set the env var for stability).
Auth applies to all `/api/*` routes except public paths and prefixes.

## Public paths (no auth required)
- `/health`, `/docs`, `/redoc`, `/openapi.json`, `/`
- `/api/v1/pool/*`, `/api/v1/pool-lease`, `/api/v1/rotation/*`, `/api/v1/config`

## Usage
```bash
# Direct
python -m agent_toolbox.start_toolbox

# Via uvicorn
uvicorn start_toolbox:app --host 0.0.0.0 --port 8000

# Via LaunchAgent
launchctl load ~/Library/LaunchAgents/com.sinator.backend.plist
```

## Caveats
- **No hot reload** by default (uvicorn reload=false). Changes require restart.
- **CDP wait**: blocks startup until Chrome on port 9222 responds, or 8s timeout.
- **GMX API check**: warns if port 8001 (gmx-alias-tool) not reachable, but starts anyway.
