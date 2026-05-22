"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — FastAPI App (V8, 2026-05-22)           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Startet die FastAPI-App mit Uvicorn und registriert alle Routen.            ║
║  Pool: 30 API Keys — ~209s/Rotation                                         ║
║                                                                              ║
║  USAGE:                                                                       ║
║  python start_toolbox.py                                                     ║
║  uvicorn start_toolbox:app --reload --host 0.0.0.0 --port 8000              ║
║                                                                              ║
║  DOCS:                                                                        ║
║  Swagger UI: http://localhost:8000/docs                                      ║
║  ReDoc:      http://localhost:8000/redoc                                     ║
║  OpenAPI:    http://localhost:8000/openapi.json                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Projekt-Root zum Path hinzufügen (Parent-Dir damit 'agent_toolbox' als Modul gefunden wird)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "agent_toolbox" / "core"))  # cua_helper, gmx_service, etc.

from agent_toolbox.api.routes.browser import router as browser_router
from agent_toolbox.api.routes.gmx import router as gmx_router
from agent_toolbox.api.routes.fireworks import router as fireworks_router
from agent_toolbox.api.routes.cookies import router as cookies_router
from agent_toolbox.api.routes.pool import router as pool_router
from agent_toolbox.api.routes.rotation import router as rotation_router

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent / "toolbox.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle-Handler für Startup und Shutdown."""
    logger.info("🚀 SINator Agent Toolbox startet...")
    logger.info(f"📂 Projekt-Root: {project_root}")
    logger.info("📖 Swagger UI: http://localhost:8000/docs")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as http:
            r = await http.get("http://localhost:8001/health")
            if r.status_code == 200:
                logger.info("✅ GMX Alias API erreichbar auf Port 8001")
            else:
                logger.warning(f"⚠️ GMX Alias API auf Port 8001: status={r.status_code}")
    except Exception:
        logger.warning("⚠️ GMX Alias API NICHT erreichbar auf Port 8001 — ./start.sh in gmx-alias-tool/ starten!")

    yield
    logger.info("🛑 SINator Agent Toolbox fährt herunter...")
    try:
        from agent_toolbox.core.browser_manager import get_browser_manager
        browser_mgr = get_browser_manager()
        if browser_mgr.is_running:
            await browser_mgr.stop()
            logger.info("✅ Browser aufgeräumt")
    except Exception as e:
        logger.warning(f"⚠️ Browser-Cleanup Fehler: {e}")

# FastAPI App erstellen
app = FastAPI(
    title="SINator Agent Toolbox",
    description="FastAPI-basierte Automatisierungs-Toolbox für GMX Alias-Erstellung und Fireworks AI Account-Rotation",
    version="8.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routen registrieren
app.include_router(browser_router, prefix="/api/v1")
app.include_router(gmx_router, prefix="/api/v1")
app.include_router(fireworks_router, prefix="/api/v1")
app.include_router(cookies_router, prefix="/api/v1")
app.include_router(pool_router, prefix="/api/v1")
app.include_router(rotation_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    """Health-Check Endpoint."""
    return {
        "service": "SINator Agent Toolbox",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Detaillierter Health-Check."""
    from agent_toolbox.core.browser_manager import get_browser_manager

    browser_mgr = get_browser_manager()
    result = {
        "status": "healthy",
        "browser_running": browser_mgr.is_running,
        "cdp_port": browser_mgr.cdp_port if browser_mgr.is_running else None,
        "gmx_alias_api": "unknown",
    }
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as http:
            r = await http.get("http://localhost:8001/health")
            result["gmx_alias_api"] = "healthy" if r.status_code == 200 else f"status_{r.status_code}"
    except Exception:
        result["gmx_alias_api"] = "unreachable"
    return result


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("TOOLBOX_PORT", "8000"))
    host = os.getenv("TOOLBOX_HOST", "0.0.0.0")
    reload = os.getenv("TOOLBOX_RELOAD", "false").lower() == "true"

    logger.info(f"🌐 Starte Uvicorn auf {host}:{port} (reload={reload})")

    uvicorn.run(
        "start_toolbox:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
