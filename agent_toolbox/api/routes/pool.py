"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Pool Routes                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINTS:                                                                   ║
║  GET  /pool/stats        → API-Key-Pool Status                              ║
║  POST /pool/add          → API-Key zum Pool hinzufügen                      ║
║  POST /pool/use          → API-Key als verwendet markieren                  ║
║  DELETE /pool/{key_id}   → API-Key aus Pool löschen                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging

from fastapi import APIRouter, HTTPException

from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.api.schemas import (
    PoolStatsResponse,
    PoolAddKeyRequest,
    PoolAddKeyResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pool", tags=["API Key Pool"])


@router.get("/stats", response_model=PoolStatsResponse)
async def get_pool_stats():
    """
    Liefert Statistiken über den API-Key-Pool.
    """
    start_time = time.time()
    pool_mgr = get_pool_manager()

    try:
        stats = pool_mgr.get_stats()
        elapsed = time.time() - start_time

        return PoolStatsResponse(
            status="success",
            total=stats["total"],
            used=stats["used"],
            available=stats["available"],
            keys=stats["keys"],
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Pool-Statistiken fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add", response_model=PoolAddKeyResponse)
async def add_key_to_pool(request: PoolAddKeyRequest):
    """
    Fügt einen neuen API-Key zum Pool hinzu.
    """
    start_time = time.time()
    pool_mgr = get_pool_manager()

    try:
        result = pool_mgr.add_key(
            api_key=request.api_key,
            alias_email=request.alias_email,
            key_name=request.key_name,
        )
        elapsed = time.time() - start_time

        return PoolAddKeyResponse(
            status="success",
            key_id=result["key_id"],
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Key-Hinzufügung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/use")
async def mark_key_used(key_id: str):
    """
    Markiert einen API-Key als verwendet.
    """
    start_time = time.time()
    pool_mgr = get_pool_manager()

    try:
        success = pool_mgr.mark_used(key_id)
        elapsed = time.time() - start_time

        return {
            "status": "success" if success else "not_found",
            "key_id": key_id,
            "execution_time": f"{elapsed:.2f}s",
        }

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Key-Markierung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{key_id}")
async def delete_key(key_id: str):
    """
    Löscht einen API-Key aus dem Pool.
    """
    start_time = time.time()
    pool_mgr = get_pool_manager()

    try:
        success = pool_mgr.delete_key(key_id)
        elapsed = time.time() - start_time

        return {
            "status": "success" if success else "not_found",
            "key_id": key_id,
            "execution_time": f"{elapsed:.2f}s",
        }

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Key-Löschung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))
