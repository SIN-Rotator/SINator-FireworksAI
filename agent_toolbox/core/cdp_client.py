"""
SINATOR AGENT-TOOLBOX — Raw CDP Client (Vereinfacht v2026-05-28)

Chrome DevTools Protocol via raw websocket. Kein Playwright, kein Puppeteer.
Nur websockets + asyncio.

Nutzt den BROWSER-WS-ENDPOINT vom laufenden Chrome (Port 9222).

Docs: cdp_client.doc.md
"""
import asyncio
import json
import base64
import logging
import websockets
from typing import Optional, Dict, Any, Callable, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OopifContext:
    """OOPIF (Cross-Origin Iframe) Offset-Container."""
    parent_session_id: str
    child_session_id: str
    offset_x: float
    offset_y: float
    width: float
    height: float
    target_id: str = ""
    iframe_url: str = ""

    def to_top(self, local_x: float, local_y: float) -> Tuple[float, float]:
        return (self.offset_x + local_x, self.offset_y + local_y)

    def contains(self, top_x: float, top_y: float) -> bool:
        return (self.offset_x <= top_x <= self.offset_x + self.width
                and self.offset_y <= top_y <= self.offset_y + self.height)


class CDPClient:
    """Raw CDP via websocket. Minimale, robuste Implementierung."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._next_id = 1
        self._pending: Dict[int, asyncio.Future] = {}
        self._handlers: Dict[str, Callable] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False

    async def connect(self, timeout: float = 10.0):
        """Verbindet zum CDP websocket endpoint."""
        logger.info(f"CDPClient: Verbinde zu {self.ws_url[:50]}...")
        self.ws = await asyncio.wait_for(
            websockets.connect(self.ws_url),
            timeout=timeout,
        )
        self._connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info("CDPClient: Verbunden")

    async def disconnect(self):
        self._connected = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
        logger.info("CDPClient: Getrennt")

    def _get_next_id(self) -> int:
        req_id = self._next_id
        self._next_id += 1
        return req_id

    async def _receive_loop(self):
        try:
            while self._connected:
                message = await self.ws.recv()
                data = json.loads(message)
                msg_id = data.get("id")
                method = data.get("method")
                if msg_id is not None and msg_id in self._pending:
                    future = self._pending.pop(msg_id)
                    if not future.done():
                        future.set_result(data)
                elif method:
                    handler = self._handlers.get(method)
                    if handler:
                        try:
                            handler(data.get("params", {}))
                        except Exception as e:
                            logger.warning(f"Event handler fehlgeschlagen für {method}: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("CDP websocket geschlossen")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"CDP receive loop fehler: {e}")

    async def send(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
        if not self._connected or not self.ws:
            raise RuntimeError("CDPClient nicht verbunden. Rufe connect() auf.")
        req_id = self._get_next_id()
        payload = {"id": req_id, "method": method}
        if params:
            payload["params"] = params
        future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future
        await self.ws.send(json.dumps(payload))
        try:
            data = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"CDP command {method} timeout nach {timeout}s")
        if data.get("error"):
            raise RuntimeError(f"CDP Error: {data['error']}")
        return data.get("result", {})

    async def send_to_session(self, session_id: str, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
        if not self._connected or not self.ws:
            raise RuntimeError("CDPClient nicht verbunden.")
        req_id = self._get_next_id()
        payload = {"id": req_id, "sessionId": session_id, "method": method}
        if params:
            payload["params"] = params
        future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future
        await self.ws.send(json.dumps(payload))
        try:
            data = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"CDP session command {method} timeout nach {timeout}s")
        if data.get("error"):
            raise RuntimeError(f"CDP Session Error: {data['error']}")
        return data.get("result", {})

    def on_event(self, method: str, handler: Callable):
        self._handlers[method] = handler

    # ── High-Level Helpers ──────────────────────────────────────────────

    async def get_targets(self) -> list:
        result = await self.send("Target.getTargets")
        return result.get("targetInfos", [])

    async def attach_to_target(self, target_id: str) -> str:
        result = await self.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        return result.get("sessionId", "")

    async def navigate(self, session_id: str, url: str, timeout: float = 30.0):
        return await self.send_to_session(session_id, "Page.navigate", {"url": url}, timeout=timeout)

    async def evaluate(self, session_id: str, expression: str, return_by_value: bool = True, timeout: float = 10.0):
        return await self.send_to_session(session_id, "Runtime.evaluate", {
            "expression": expression,
            "returnByValue": return_by_value,
            "awaitPromise": True,
        }, timeout=timeout)

    async def click_at(self, session_id: str, x: float, y: float, button: str = "left"):
        await self.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": button, "clickCount": 1,
        })
        await self.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": button, "clickCount": 1,
        })

    async def screenshot(self, session_id: str, format: str = "png", path: Optional[str] = None) -> str:
        try:
            result = await self.send_to_session(session_id, "Page.captureScreenshot", {"format": format, "fromSurface": True})
            data = result.get("data", "")
            if path and data:
                with open(path, "wb") as f:
                    f.write(base64.b64decode(data))
            return data
        except Exception as e:
            logger.warning(f"Screenshot fehlgeschlagen: {e}")
            return ""

    async def get_document(self, session_id: str) -> Dict[str, Any]:
        return await self.send_to_session(session_id, "DOM.getDocument", {"depth": -1, "pierce": True})

    async def query_selector(self, session_id: str, selector: str, node_id: Optional[int] = None) -> Optional[int]:
        if node_id is None:
            doc = await self.get_document(session_id)
            node_id = doc.get("root", {}).get("nodeId")
        try:
            result = await self.send_to_session(session_id, "DOM.querySelector", {"nodeId": node_id, "selector": selector})
            found_id = result.get("nodeId", 0)
            return found_id if found_id > 0 else None
        except Exception:
            return None

    async def get_box_model(self, session_id: str, node_id: int) -> Optional[Dict[str, Any]]:
        try:
            result = await self.send_to_session(session_id, "DOM.getBoxModel", {"nodeId": node_id})
            return result.get("model")
        except Exception:
            return None

    # ── OOPIF Helpers ───────────────────────────────────────────────────

    async def find_iframe_target(self, url_substring: str) -> Optional[Dict[str, Any]]:
        targets = await self.get_targets()
        for t in targets:
            if t.get("type") == "iframe" and url_substring in t.get("url", ""):
                return t
        return None

    async def attach_to_iframe(self, url_substring: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        target = await self.find_iframe_target(url_substring)
        if not target:
            return None
        session_id = await self.attach_to_target(target["targetId"])
        return session_id, target

    async def get_iframe_viewport_box(self, parent_session_id: str, iframe_selector: str) -> Optional[Tuple[float, float, float, float]]:
        try:
            doc = await self.send_to_session(parent_session_id, "DOM.getDocument", {"depth": 1})
            root_id = doc.get("root", {}).get("nodeId")
            if not root_id:
                return None
            qs = await self.send_to_session(parent_session_id, "DOM.querySelector", {"nodeId": root_id, "selector": iframe_selector})
            iframe_node = qs.get("nodeId", 0)
            if not iframe_node:
                return None
            box_res = await self.send_to_session(parent_session_id, "DOM.getBoxModel", {"nodeId": iframe_node})
            model = box_res.get("model")
            if not model:
                return None
            c = model["content"]
            return (c[0], c[1], c[2] - c[0], c[7] - c[1])
        except Exception:
            return None

    async def resolve_oopif(self, parent_session_id: str, url_substring: str, iframe_selector: str, enable_dom: bool = True) -> Optional[OopifContext]:
        attached = await self.attach_to_iframe(url_substring)
        if not attached:
            return None
        child_session_id, target = attached
        if enable_dom:
            try:
                await self.send_to_session(child_session_id, "DOM.enable")
            except Exception:
                pass
        box = await self.get_iframe_viewport_box(parent_session_id, iframe_selector)
        if not box:
            await asyncio.sleep(0.5)
            box = await self.get_iframe_viewport_box(parent_session_id, iframe_selector)
        if not box:
            return None
        x, y, w, h = box
        return OopifContext(
            parent_session_id=parent_session_id,
            child_session_id=child_session_id,
            offset_x=x, offset_y=y,
            width=w, height=h,
            target_id=target.get("targetId", ""),
            iframe_url=target.get("url", ""),
        )

    async def dom_search(self, session_id: str, query: str, include_shadow: bool = True, max_results: int = 100) -> List[int]:
        try:
            search = await self.send_to_session(session_id, "DOM.performSearch", {
                "query": query,
                "includeUserAgentShadowDOM": include_shadow,
            })
        except Exception:
            return []
        count = search.get("resultCount", 0)
        if count == 0:
            return []
        try:
            res = await self.send_to_session(session_id, "DOM.getSearchResults", {
                "searchId": search["searchId"],
                "fromIndex": 0,
                "toIndex": min(count, max_results),
            })
            return list(res.get("nodeIds", []))
        except Exception:
            return []

    async def node_content_box(self, session_id: str, node_id: int) -> Optional[Tuple[float, float, float, float]]:
        try:
            res = await self.send_to_session(session_id, "DOM.getBoxModel", {"nodeId": node_id})
            model = res.get("model")
            if not model:
                return None
            c = model["content"]
            return (c[0], c[1], c[2] - c[0], c[7] - c[1])
        except Exception:
            return None

    async def node_describe(self, session_id: str, node_id: int, depth: int = 1) -> Optional[Dict[str, Any]]:
        try:
            res = await self.send_to_session(session_id, "DOM.describeNode", {"nodeId": node_id, "depth": depth})
            return res.get("node")
        except Exception:
            return None


async def get_browser_ws_endpoint(cdp_port: int = 9222, timeout: float = 15.0) -> str:
    import urllib.request
    url = f"http://127.0.0.1:{cdp_port}/json/version"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Python/CDP"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        ws_url = data.get("webSocketDebuggerUrl")
        if ws_url:
            return ws_url
    except Exception as e:
        logger.error(f"CDP endpoint fehlgeschlagen: {e}")
    raise RuntimeError(f"Chrome DevTools nicht erreichbar auf Port {cdp_port}")


async def get_page_target(cdp_client: CDPClient, url_filter: str = "") -> Optional[Dict[str, Any]]:
    targets = await cdp_client.get_targets()
    matching = [t for t in targets if t.get("type") == "page" and (not url_filter or url_filter in t.get("url", ""))]
    non_auth = [t for t in matching if "auth.gmx.net" not in t.get("url", "")]
    if non_auth:
        return non_auth[0]
    if matching:
        return matching[0]
    for t in targets:
        if t.get("type") == "page":
            return t
    return None
