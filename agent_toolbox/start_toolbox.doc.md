# start_toolbox.py — FastAPI Application Entry

## Purpose
Starts the SINator Agent Toolbox FastAPI server with Uvicorn. Registers all API routes, CORS middleware, auth token, and static file serving.

## Dependencies
- **Imports from:** `agent_toolbox.api.routes.*` (all API routers)
- **Imported by:** CLI (`python start_toolbox.py`), Uvicorn
- **Reads:** `static/dashboard.html` (SPA)

## Routes
| Prefix | Router | Purpose |
|--------|--------|---------|
| `/api/v1` | `gmx_router` | GMX alias operations |
| `/api/v1` | `fireworks_router` | Fireworks account operations |
| `/api/v1` | `pool_router` | Pool CRUD + stats |
| `/api/v1` | `lease_router` | Key lease management |
| `/api/v1` | `rotation_router` | Full rotation orchestration |
| `/api/v1` | `config_router` | Runtime configuration |

## Auth
- Bearer token auth on `/api/*` routes
- Token: `SINATOR_AUTH_TOKEN` env var, or auto-generated `sinator-<uuid>`
- Public paths: `/health`, `/docs`, `/redoc`, `/openapi.json`, `/api/v1/pool/*`, `/api/v1/config`

## Port
Default: `8000` (override via `TOOLBOX_PORT` env var)
