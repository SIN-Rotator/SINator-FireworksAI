"""
Async HTTP client for the backend pool API (lease, return, report, stats).

Docs: pool_client.doc.md
"""
import logging
from typing import Optional, Dict, Any

import httpx

try:
    from .config import load_config
except ImportError:
    from config import load_config

logger = logging.getLogger(__name__)


class PoolClient:
    def __init__(self, pool_api_url: Optional[str] = None):
        cfg = load_config()
        self.pool_api_url = pool_api_url or cfg.get("pool_api_url", "http://localhost:8000/api/v1")
        self.lease_ttl = cfg.get("lease_ttl_seconds", 1800)
        self.lease_backup = cfg.get("lease_backup", False)
        self._http = httpx.AsyncClient(timeout=15.0)

    async def lease(self, leased_to: str = "proxy") -> Optional[Dict[str, Any]]:
        try:
            r = await self._http.post(
                f"{self.pool_api_url}/pool/lease",
                json={
                    "ttl_seconds": self.lease_ttl,
                    "leased_to": leased_to,
                    "lease_backup": self.lease_backup,
                },
            )
            if r.status_code == 200:
                data = r.json()
                logger.info(f"Leased key: {data.get('key_id', '?')[:8]}... (lease={data.get('lease_id')})")
                return data
            elif r.status_code == 404:
                logger.error("No available keys to lease!")
                return None
            else:
                logger.error(f"Lease failed: {r.status_code} {r.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Lease request failed: {e}")
            return None

    async def return_key(self, key_id: str, lease_id: Optional[str] = None) -> bool:
        try:
            body = {"key_id": key_id}
            if lease_id:
                body["lease_id"] = lease_id
            r = await self._http.post(f"{self.pool_api_url}/pool/return", json=body)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Return failed: {e}")
            return False

    async def report(self, api_key: Optional[str] = None, key_id: Optional[str] = None,
                     reason: str = "unknown", leased_to: str = "proxy") -> Optional[Dict[str, Any]]:
        try:
            body = {
                "reason": reason,
                "leased_to": leased_to,
                "ttl_seconds": self.lease_ttl,
            }
            if api_key:
                body["api_key"] = api_key
            if key_id:
                body["key_id"] = key_id
            r = await self._http.post(f"{self.pool_api_url}/pool/report", json=body)
            if r.status_code == 200:
                data = r.json()
                logger.info(f"Reported key ({reason}), swap result: {data.get('status')}")
                return data
            elif r.status_code == 404:
                logger.warning(f"Reported key not found in pool")
                return None
            else:
                logger.error(f"Report failed: {r.status_code} {r.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Report request failed: {e}")
            return None

    async def stats(self) -> Optional[Dict[str, Any]]:
        try:
            r = await self._http.get(f"{self.pool_api_url}/pool/stats")
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            logger.error(f"Stats request failed: {e}")
            return None

    async def close(self):
        await self._http.aclose()
