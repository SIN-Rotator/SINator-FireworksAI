"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Pool Routes                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINTS:                                                                   ║
║  GET  /pool/stats        → API-Key-Pool Status                              ║
║  POST /pool/add          → API-Key zum Pool hinzufügen                      ║
║  POST /pool/use          → (legacy) API-Key als verwendet markieren         ║
║  GET  /pool/key          → (legacy) Nächsten verfügbaren API-Key (Klartext) ║
║  POST /pool/lease        → Key leasen (atomic, mit TTL)                     ║
║  POST /pool/return       → Geleaste Key zurückgeben                         ║
║  POST /pool/report       → Bad key melden + Ersatz                          ║
║  GET  /pool/events       → SSE Stream für Dashboard Live-Updates            ║
║  POST /pool/agent-key        → V19.14 Soft-Ownership Key-Zuweisung         ║
║  POST /pool/agent-release    → V19.14 Agent gibt Key frei                  ║
║  POST /pool/agent-heartbeat  → V19.14 Agent Heartbeat                      ║
║  GET  /pool/health       → Validiert alle Keys via Fireworks API            ║
║  DELETE /pool/{key_id}   → API-Key aus Pool löschen                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
Docs: pool.doc.md
"""
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent_toolbox.core.pool_manager import (
    get_pool_manager,
    register_sse_listener,
    unregister_sse_listener,
    _emit_event,
)
from agent_toolbox.api.schemas import (
    PoolStatsResponse,
    PoolAddKeyRequest,
    PoolAddKeyResponse,
)
from agent_toolbox.core.keychain_store import migrate_pool as _migrate_pool, hydrate_single as _hydrate_single

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pool", tags=["API Key Pool"])
lease_router = APIRouter(tags=["Pool Lease"])  # no prefix — for /pool-lease (Dashboard)


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
            suspended=stats.get("suspended", 0),
            leased=stats.get("leased", 0),
            active_in_use=stats.get("active_in_use", 0),
            available=stats["available"],
            assigned=stats.get("assigned", 0),
            shared=stats.get("shared", 0),
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


@router.get("/key")
async def get_api_key():
    """
    Liefert den nächsten verfügbaren API-Key (hydratisiert aus Keychain).
    """
    pool_mgr = get_pool_manager()
    key = pool_mgr.get_available_key()
    if not key:
        raise HTTPException(status_code=404, detail="No available API keys")
    return {
        "status": "success",
        "api_key": key.get("api_key"),
        "key_id": key.get("id"),
        "alias_email": key.get("alias_email"),
    }


@router.post("/report")
async def report_bad_key(request: dict):
    """
    Key als verbraucht melden (Rate-Limit/Suspended).
    Markiert den Key als used und liefert einen neuen.
    
    Body: {"api_key": "fw_xxx"} oder {"key_id": "xxx"}
    Optional: {"reason": "suspended" | "rate_limited" | "unauthorized" | "credits_exhausted"}
    
    Returns:
      200 + swapped=true + new_key wenn Key gefunden und markiert wurde
      404 wenn der gemeldete Key nicht im Pool existiert
      400 wenn kein api_key oder key_id angegeben wurde
    """
    pool_mgr = get_pool_manager()
    key_id = request.get("key_id") or request.get("id")
    api_key = request.get("api_key") or request.get("key")
    reason = request.get("reason", "unknown")

    if not key_id and not api_key:
        raise HTTPException(status_code=400, detail="Missing 'api_key' or 'key_id' in request body")

    leased_to = request.get("leased_to", "proxy")
    ttl_seconds = request.get("ttl_seconds", 1800)
    result = pool_mgr.report_key(
        api_key=api_key, key_id=key_id, reason=reason,
        leased_to=leased_to, ttl_seconds=ttl_seconds,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Key '{api_key or key_id}' not found in pool"
        )

    return {
        "status": result.get("status", "success"),
        "swapped": result.get("swapped", False),
        "new_key": result.get("new_api_key"),
        "new_key_id": result.get("new_key_id"),
        "new_alias": result.get("new_alias"),
        "new_key_name": result.get("new_key_name", ""),
        "lease_id": result.get("lease_id"),
        "expires_at": result.get("expires_at"),
        "reason": reason,
    }


@lease_router.get("/pool-lease")
async def lease_key_get(leased_to: str = "dashboard", ttl_seconds: int = 1800):
    """Lease a key via GET (Dashboard compatibility — same as POST /pool/lease)."""
    pool_mgr = get_pool_manager()
    result = pool_mgr.lease_key(ttl_seconds=ttl_seconds, leased_to=leased_to)
    if not result:
        raise HTTPException(status_code=404, detail="No available keys to lease")
    # Hydrate api_key from keychain if it's still the SENTINEL placeholder.
    if not result.get("api_key"):
        hydrated = _hydrate_single(dict(result))
        if hydrated.get("api_key"):
            result["api_key"] = hydrated["api_key"]
    return {
        "status": "success",
        "api_key": result["api_key"],
        "key_id": result["key_id"],
        "lease_id": result["lease_id"],
        "expires_at": result["expires_at"],
        "alias_email": result["alias_email"],
        "key_name": result.get("key_name", ""),
    }


@router.post("/lease")
async def lease_key(request: dict):
    """
    Lease an available key atomically with TTL.
    
    Body: {
      "ttl_seconds": 1800,        // Lease duration (default 30min)
      "leased_to": "proxy-1",     // Identifier of lessee
      "lease_backup": false       // Also lease a backup key?
    }
    
    Returns:
      200 + key info + lease_id + expires_at
      404 if no available keys
    """
    pool_mgr = get_pool_manager()
    ttl_seconds = request.get("ttl_seconds", 1800)
    leased_to = request.get("leased_to", "proxy")
    lease_backup = request.get("lease_backup", False)

    result = pool_mgr.lease_key(
        ttl_seconds=ttl_seconds,
        leased_to=leased_to,
        lease_backup=lease_backup,
    )

    if not result:
        raise HTTPException(status_code=404, detail="No available keys to lease")

    # Hydrate api_key from keychain if it's still the SENTINEL placeholder.
    if not result.get("api_key"):
        hydrated = _hydrate_single(dict(result))
        if hydrated.get("api_key"):
            result["api_key"] = hydrated["api_key"]
        if result.get("backup") and not result["backup"].get("api_key"):
            backup_hydrated = _hydrate_single(dict(result["backup"]))
            if backup_hydrated.get("api_key"):
                result["backup"]["api_key"] = backup_hydrated["api_key"]

    return {
        "status": "success",
        "api_key": result["api_key"],
        "key_id": result["key_id"],
        "lease_id": result["lease_id"],
        "expires_at": result["expires_at"],
        "alias_email": result["alias_email"],
        "key_name": result.get("key_name", ""),
        "backup": result.get("backup"),
    }


@router.post("/return")
async def return_leased_key(request: dict):
    """
    Return a leased key, making it available again.
    
    Body: {"key_id": "xxx"} or {"key_id": "xxx", "lease_id": "yyy"}
    
    Returns:
      200 if key was returned
      404 if key not found
      400 if lease_id mismatch
    """
    pool_mgr = get_pool_manager()
    key_id = request.get("key_id")
    lease_id = request.get("lease_id")

    if not key_id:
        raise HTTPException(status_code=400, detail="Missing 'key_id' in request body")

    success = pool_mgr.return_key(key_id=key_id, lease_id=lease_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Key '{key_id}' not found or lease_id mismatch")

    return {"status": "success", "key_id": key_id}


@router.post("/agent-key")
async def get_agent_key(request: dict):
    """V19.14: Soft-ownership key assignment — never blocks.

    Body: {
      "agent_id": "opencode-main-a3f8b2c1",  // required
      "preferred_key_id": "uuid..."          // optional, for sticky
    }

    Returns:
      200 + key info, shared flag, active_consumers count
      409 if no keys available (all suspended/used)
    """
    pool_mgr = get_pool_manager()
    agent_id = request.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="Missing 'agent_id' in request body")
    
    preferred_key_id = request.get("preferred_key_id")
    result = pool_mgr.get_key_for_agent(
        agent_id=agent_id,
        preferred_key_id=preferred_key_id,
    )
    
    if not result:
        raise HTTPException(status_code=409, detail="No keys available (all suspended/used)")
    
    # Safety hydration (belt-and-suspenders, same as /lease)
    if not result.get("api_key"):
        hydrated = _hydrate_single(dict(result))
        if hydrated.get("api_key"):
            result["api_key"] = hydrated["api_key"]
    
    return {
        "status": "success",
        "api_key": result["api_key"],
        "key_id": result["key_id"],
        "alias_email": result.get("alias_email", ""),
        "key_name": result.get("key_name", ""),
        "shared": result.get("shared", False),
        "active_consumers": result.get("active_consumers", []),
        "assigned_to": result.get("assigned_to"),
        "shared_count": result.get("shared_count", 0),
    }


@router.post("/agent-release")
async def release_agent_key(request: dict):
    """V19.14: Agent releases a key.
    
    Body: {"agent_id": "...", "key_id": "..."}
    
    Returns:
      200 if key was released
      404 if key not found
    """
    pool_mgr = get_pool_manager()
    agent_id = request.get("agent_id")
    key_id = request.get("key_id")
    
    if not agent_id or not key_id:
        raise HTTPException(status_code=400, detail="Missing 'agent_id' or 'key_id'")
    
    success = pool_mgr.release_key_for_agent(agent_id=agent_id, key_id=key_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Key '{key_id}' not found")
    
    return {"status": "success", "released": True, "key_id": key_id}


@router.post("/agent-heartbeat")
async def agent_heartbeat(request: dict):
    """V19.14: Agent sends heartbeat to keep active_consumers alive.
    
    Body: {"agent_id": "...", "key_id": "..."}
    
    Returns:
      200 always (heartbeat is fire-and-forget)
    """
    pool_mgr = get_pool_manager()
    agent_id = request.get("agent_id")
    key_id = request.get("key_id")
    
    if not agent_id or not key_id:
        raise HTTPException(status_code=400, detail="Missing 'agent_id' or 'key_id'")
    
    pool_mgr.reload()
    for k in pool_mgr.keys:
        if k["id"] == key_id:
            k["last_heartbeat"] = time.time()
            pool_mgr.save()
            break
    
    return {"status": "success", "heartbeat": True}


@router.get("/events")
async def pool_events():
    """
    SSE stream for dashboard live updates.
    
    Events:
      key_leased   — key was leased by a proxy
      key_returned — key was returned
      key_swapped  — bad key was swapped for a new one
      stats        — periodic pool stats update (every 30s)
    """
    queue = register_sse_listener()

    async def event_generator():
        try:
            stats_interval = 30
            last_stats = time.time()
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                    event_type = payload.get("event", "stats")
                    data = payload.get("data", {})
                    yield f"event: {event_type}\ndata: {__import__('json').dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    pass
                now = time.time()
                if now - last_stats >= stats_interval:
                    pool_mgr = get_pool_manager()
                    stats = pool_mgr.get_stats()
                    yield f"event: stats\ndata: {__import__('json').dumps({'total': stats['total'], 'used': stats['used'], 'leased': stats['leased'], 'available': stats['available']})}\n\n"
                    last_stats = now
        except asyncio.CancelledError:
            pass
        finally:
            unregister_sse_listener(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/reload")
async def reload_pool():
    """Reload the in-memory pool from disk. Called by auto_sync.py after v2→v3 sync."""
    pool_mgr = get_pool_manager()
    pool_mgr.reload()
    stats = pool_mgr.get_stats()
    _emit_event("stats", {
        "total": stats["total"],
        "available": stats["available"],
        "used": stats["used"],
        "suspended": stats["suspended"],
        "leased": stats["leased"],
    })
    return {"status": "success", "total": len(pool_mgr.keys)}


@router.get("/health")
async def check_pool_health(deep_check: bool = False):
    """
    Validiert ALLE Pool-Keys via Fireworks API.
    Markiert gesperrte Keys (401/402/403/412) automatisch als used.

    Query-Parameter:
      deep_check=false  — nur HTTP-Health-Check (schnell)
      deep_check=true   — zusätzlich CDP-Billing-Check für aktive Keys (langsam)
    """
    import httpx
    import asyncio
    import json
    from pathlib import Path
    from agent_toolbox.core.keychain_store import retrieve_key as _retrieve_from_keychain, SENTINEL as _KC_SENTINEL

    pool_path = Path("data/fireworksai-pool.json")
    if not pool_path.exists():
        return {"status": "empty", "healthy": 0, "suspended": 0, "total": 0, "checked": []}

    all_keys = json.loads(pool_path.read_text())
    if not all_keys:
        return {"status": "empty", "healthy": 0, "suspended": 0, "total": 0, "checked": []}

    async def check_key(k: dict) -> dict:
        key_id = k.get("id", "?")
        raw_api_key = k.get("api_key", "")
        if raw_api_key == _KC_SENTINEL:
            api_key = _retrieve_from_keychain(key_id) or ""
        else:
            api_key = raw_api_key
        email = k.get("alias_email", "?")
        result = {
            "key_id": key_id, "email": email, "status": "unknown",
            "credits_initial": k.get("credits_initial", 6.0),
            "credits_remaining": k.get("credits_remaining"),
            "credits_checked_at": k.get("credits_checked_at"),
        }

        if not api_key:
            result["status"] = "no_key"
            return result

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.fireworks.ai/inference/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if r.status_code == 200:
                    result["status"] = "healthy"
                elif r.status_code in (401, 402, 403, 412):
                    result["status"] = "suspended"
                else:
                    result["status"] = f"error_{r.status_code}"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)[:100]

        return result

    results = await asyncio.gather(*[check_key(k) for k in all_keys])
    healthy = sum(1 for r in results if r["status"] == "healthy")
    suspended = sum(1 for r in results if r["status"] == "suspended")
    total_credits = sum(r.get("credits_remaining", 0) or 0 for r in results if r.get("credits_remaining"))

    return {
        "status": "success",
        "total": len(results),
        "healthy": healthy,
        "suspended": suspended,
        "total_credits_remaining": round(total_credits, 2),
        "checked": results,
    }


@router.get("/reveal/{key_id}")
async def reveal_key(key_id: str):
    """
    Gibt den echten API-Key für einen Pool-Eintrag zurück (aus Keychain).
    Nur für localhost/Tauri Dashboard — nicht öffentlich exponieren.
    """
    pool_mgr = get_pool_manager()
    pool_mgr.reload()
    for k in pool_mgr.keys:
        if k["id"] == key_id:
            hydrated = pool_mgr._hydrate_key(k)
            return {
                "status": "success",
                "api_key": hydrated.get("api_key", ""),
                "key_id": key_id,
                "alias_email": k.get("alias_email", ""),
            }
    raise HTTPException(status_code=404, detail="Key not found")


@router.post("/migrate-to-keychain")
async def migrate_to_keychain(dry_run: bool = False):
    """
    Migriert alle Plaintext API-Keys in macOS Keychain.
    Nach der Migration enthält die Pool-JSON nur noch SENTINEL-Werte.
    
    Query-Parameter:
      dry_run=true  — nur zählen, nicht wirklich migrieren
    """
    from agent_toolbox.core.pool_manager import DEFAULT_POOL_PATH
    result = _migrate_pool(DEFAULT_POOL_PATH, dry_run=dry_run)
    return result


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
