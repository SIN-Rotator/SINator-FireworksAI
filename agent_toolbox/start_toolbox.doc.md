# FastAPI App Entry (`start_toolbox.py`)

Main entry point for the SINator Agent Toolbox FastAPI application. Registers all API route routers, configures CORS, static files, auth middleware, and waits for Chrome CDP before starting Uvicorn.

## Dependencies

- **Imported by:** run directly (`python start_toolbox.py` or `uvicorn start_toolbox:app`)
- **Imports:** `fastapi`, `uvicorn`, all route routers (`gmx`, `fireworks`, `pool`, `rotation`, `config`)

## Key Routes

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Root health check |
| `/health` | GET | Detailed health (Chrome, CUA status) |
| `/dashboard` | GET | Serve dashboard HTML SPA |
| `/docs` | GET | Swagger UI |
| `/redoc` | GET | ReDoc |
| `/api/v1/gmx/...` | * | GMX operations (via `gmx_router`) |
| `/api/v1/fireworks/...` | * | Fireworks operations (via `fireworks_router`) |
| `/api/v1/pool/...` | * | Pool CRUD + stats (via `pool_router`) |
| `/api/v1/pool-lease/...` | * | Pool lease operations (via `lease_router`) |
| `/api/v1/rotation/...` | * | Full rotation orchestrator (via `rotation_router`) |
| `/api/v1/config/...` | * | Config management (via `config_router`) |

## Auth

- Public paths: `/health`, `/docs`, `/redoc`, `/openapi.json`, `/`
- Public prefixes: `/api/v1/pool/`, `/api/v1/pool-lease`, `/api/v1/rotation/`, `/api/v1/config`
- All other `/api/*` routes require `Authorization: Bearer <token>`
- Token from `SINATOR_AUTH_TOKEN` env var, or auto-generated per-run

## Startup Sequence

1. Register all routers
2. Wait for Chrome CDP on port 9222 (configurable via `SINATOR_CDP_WAIT`)
3. Check GMX Alias API on port 8001 (non-fatal)
4. Start Uvicorn on configurable host/port

## Config

| Env Var | Default | Purpose |
|---------|---------|---------|
| `TOOLBOX_PORT` | `8000` | HTTP listen port |
| `TOOLBOX_HOST` | `0.0.0.0` | HTTP bind address |
| `TOOLBOX_RELOAD` | `false` | Enable auto-reload for development |
| `SINATOR_CDP_WAIT` | `8` | Seconds to wait for Chrome CDP |
| `SINATOR_AUTH_TOKEN` | auto-generated | Bearer token for API auth |
