"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Raw CDP Client                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Chrome DevTools Protocol (CDP) via raw websocket.                            ║
║  BYPASST Playwright's frame-tracking crash auf GMX SPA.                   ║
║                                                                              ║
║  WARUM RAW CDP?                                                              ║
║  Playwright crashed bei GMX Navigator SPA mit:                               ║
║    ValueError: list.remove(x): x not in list                                 ║
║    playwright/_impl/_page.py:279                                               ║
║  Ursache: GMX entfernt iframes/shadow-roots dynamisch. Playwright's          ║
║  internal frame-registry kann nicht damit umgehen.                           ║
║                                                                              ║
║  LÖSUNG: Direkte CDP-Websocket-Kommunikation ohne Playwright-Page-Wrapper.  ║
║  Wir sprechen direkt mit Chrome's DevTools Protocol über websocket.          ║
║                                                                              ║
║  CDP COMMANDS (wichtige für GMX):                                            ║
║  • Input.dispatchMouseEvent  → Klicks im Shadow DOM / SPA                    ║
║  • Runtime.evaluate          → JS ausführen (auch in iframes)                ║
║  • Page.captureScreenshot    → Screenshots für Debugging                     ║
║  • Page.navigate             → URL laden                                     ║
║  • DOM.querySelector         → Elemente finden                               ║
║  • DOM.getBoxModel           → Koordinaten für Klicks                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import asyncio
import json
import base64
import logging
import websockets
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CDPResponse:
    """Strukturierte CDP Response."""
    id: Optional[int]
    result: Optional[Dict[str, Any]]
    error: Optional[Dict[str, Any]]
    method: Optional[str]  # Für async events (notifications)
    params: Optional[Dict[str, Any]]


class CDPClient:
    """
    Raw Chrome DevTools Protocol Client via websocket.
    
    BYPASST komplett Playwright's Page-Objekt für GMX-Operationen.
    Jeder Command hat eine eindeutige ID. Responses werden via ID gematcht.
    Async events (z.B. Page.loadEventFired) haben keine ID (id=null).
    
    Usage:
        client = CDPClient("ws://127.0.0.1:9222/devtools/browser/...")
        await client.connect()
        
        # Tab/Seite ansprechen
        result = await client.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = result["sessionId"]
        
        # Mouse click
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": 80, "y": 290, "button": "left", "clickCount": 1
        })
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": 80, "y": 290, "button": "left", "clickCount": 1
        })
        
        # JS evaluieren
        result = await client.send_to_session(session_id, "Runtime.evaluate", {
            "expression": "document.title",
            "returnByValue": True
        })
        title = result["result"]["value"]
    """

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._next_id = 1
        self._pending: Dict[int, asyncio.Future] = {}
        self._handlers: Dict[str, Callable] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False

    async def connect(self):
        """Verbindet zum CDP websocket endpoint."""
        logger.info(f"CDPClient: Verbinde zu {self.ws_url[:50]}...")
        self.ws = await websockets.connect(self.ws_url)
        self._connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info("CDPClient: Verbunden")

    async def disconnect(self):
        """Trennt die Verbindung."""
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
        """Generiert eindeutige Request-ID."""
        req_id = self._next_id
        self._next_id += 1
        return req_id

    async def _receive_loop(self):
        """
        Background-Task: Empfängt alle websocket messages.
        
        CDP Protocol Format:
        - Command Response:  {"id": 1, "result": {...}} oder {"id": 1, "error": {...}}
        - Event/Notification: {"method": "Page.loadEventFired", "params": {...}}
        
        Wichtig: Events haben KEINE id (oder id=null). Nur command responses haben id.
        """
        try:
            while self._connected:
                message = await self.ws.recv()
                data = json.loads(message)
                
                msg_id = data.get("id")
                method = data.get("method")
                
                if msg_id is not None and msg_id in self._pending:
                    # Das ist eine Response auf einen pending command
                    future = self._pending.pop(msg_id)
                    future.set_result(CDPResponse(
                        id=msg_id,
                        result=data.get("result"),
                        error=data.get("error"),
                        method=None,
                        params=None,
                    ))
                elif method:
                    # Das ist ein async event (z.B. Page.loadEventFired)
                    handler = self._handlers.get(method)
                    if handler:
                        try:
                            handler(data.get("params", {}))
                        except Exception as e:
                            logger.warning(f"Event handler fehlgeschlagen für {method}: {e}")
                    else:
                        logger.debug(f"Unbehandeltes CDP Event: {method}")
                        
        except websockets.exceptions.ConnectionClosed:
            logger.info("CDP websocket geschlossen")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"CDP receive loop fehler: {e}")

    async def send(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Sendet einen CDP Command und wartet auf die Response.
        
        Args:
            method: CDP Method name (z.B. "Page.navigate")
            params: Method parameters
            timeout: Max wait time in seconds
            
        Returns:
            Das "result" Dict aus der CDP Response
            
        Raises:
            Exception: Wenn error in response oder timeout
        """
        if not self._connected or not self.ws:
            raise RuntimeError("CDPClient nicht verbunden. Rufe connect() auf.")

        req_id = self._get_next_id()
        payload = {"id": req_id, "method": method}
        if params:
            payload["params"] = params

        # Future erstellen BEVOR wir senden (race condition vermeiden)
        future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        await self.ws.send(json.dumps(payload))
        logger.debug(f"CDP >> [{req_id}] {method}")

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"CDP command {method} timeout nach {timeout}s")

        if response.error:
            raise RuntimeError(f"CDP Error: {response.error}")

        logger.debug(f"CDP << [{req_id}] {method} OK")
        return response.result or {}

    async def send_to_session(self, session_id: str, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Sendet einen CDP Command an eine bestimmte Session (z.B. einen Tab).
        
        CDP Flatten Mode: Commands an eine Session werden mit sessionId prefixed:
        {"id": 1, "sessionId": "...", "method": "...", "params": {...}}
        
        Args:
            session_id: Die Session ID des Tabs/Targets
            method: CDP Method name
            params: Method parameters
            timeout: Max wait time
            
        Returns:
            Das "result" Dict
        """
        if not self._connected or not self.ws:
            raise RuntimeError("CDPClient nicht verbunden.")

        req_id = self._get_next_id()
        payload = {"id": req_id, "sessionId": session_id, "method": method}
        if params:
            payload["params"] = params

        future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        await self.ws.send(json.dumps(payload))
        logger.debug(f"CDP >> [{req_id}][{session_id[:8]}...] {method}")

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"CDP session command {method} timeout nach {timeout}s")

        if response.error:
            raise RuntimeError(f"CDP Session Error: {response.error}")

        logger.debug(f"CDP << [{req_id}] {method} OK")
        return response.result or {}

    def on_event(self, method: str, handler: Callable):
        """Registriert einen Handler für CDP events (z.B. Page.loadEventFired)."""
        self._handlers[method] = handler
        logger.info(f"Event handler registriert für {method}")

    # ═══════════════════════════════════════════════════════════════════════════════
    #  HIGH-LEVEL HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════════

    async def get_targets(self) -> list:
        """Listet alle offenen Tabs/Targets auf."""
        result = await self.send("Target.getTargets")
        return result.get("targetInfos", [])

    async def attach_to_target(self, target_id: str) -> str:
        """
        Attached zu einem Target (Tab) und gibt die Session ID zurück.
        
        Args:
            target_id: Die targetId aus get_targets()
            
        Returns:
            sessionId für send_to_session()
        """
        result = await self.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = result.get("sessionId")
        logger.info(f"Attached zu target {target_id[:15]}..., session={session_id[:15]}...")
        return session_id

    async def navigate(self, session_id: str, url: str, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Navigiert zu einer URL via CDP.
        
        Returns:
            {"frameId": "...", "loaderId": "..."}
        """
        return await self.send_to_session(session_id, "Page.navigate", {"url": url}, timeout=timeout)

    async def evaluate(self, session_id: str, expression: str, return_by_value: bool = True, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Führt JavaScript im Page-Kontext aus.
        
        Args:
            session_id: CDP Session ID
            expression: JavaScript code
            return_by_value: Wenn True, wird das Ergebnis serialisiert zurückgegeben
            
        Returns:
            CDP Runtime.evaluate result (enthält "result" mit "value" oder "objectId")
        """
        return await self.send_to_session(session_id, "Runtime.evaluate", {
            "expression": expression,
            "returnByValue": return_by_value,
            "awaitPromise": True,
        }, timeout=timeout)

    async def click_at(self, session_id: str, x: float, y: float, button: str = "left"):
        """
        Führt einen Mouse-Click an bestimmten Koordinaten aus.
        
        WICHTIG für GMX: Die Navigator-SPA hat Shadow-DOM Elemente die nicht
        via DOM.querySelector gefunden werden können. Coordinate-basiertes
        Klicken ist die zuverlässigste Methode.
        
        CDP Mouse Event Sequence:
        1. mousePressed  (Taste drücken)
        2. mouseReleased (Taste loslassen)
        
        Args:
            session_id: CDP Session ID
            x: X-Koordinate
            y: Y-Koordinate
            button: "left", "right", "middle"
        """
        logger.info(f"CDP Click bei ({x}, {y})")
        await self.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": x, "y": y,
            "button": button,
            "clickCount": 1,
        })
        await self.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": x, "y": y,
            "button": button,
            "clickCount": 1,
        })

    async def screenshot(self, session_id: str, format: str = "png", path: Optional[str] = None) -> str:
        """
        Macht einen Screenshot der Page.
        
        Args:
            session_id: CDP Session ID
            format: "png" oder "jpeg"
            path: Wenn angegeben, wird das Bild gespeichert
            
        Returns:
            Base64-kodierte Bilddaten (oder leerer String wenn error)
        """
        try:
            result = await self.send_to_session(session_id, "Page.captureScreenshot", {
                "format": format,
                "fromSurface": True,
            })
            data = result.get("data", "")
            
            if path and data:
                with open(path, "wb") as f:
                    f.write(base64.b64decode(data))
                logger.info(f"Screenshot gespeichert: {path}")
                
            return data
        except Exception as e:
            logger.warning(f"Screenshot fehlgeschlagen: {e}")
            return ""

    async def get_document(self, session_id: str) -> Dict[str, Any]:
        """Holt das root DOM node (document)."""
        return await self.send_to_session(session_id, "DOM.getDocument", {"depth": -1, "pierce": True})

    async def query_selector(self, session_id: str, selector: str, node_id: Optional[int] = None) -> Optional[int]:
        """
        Findet ein Element via CSS Selector im DOM.
        
        Args:
            session_id: CDP Session ID
            selector: CSS Selector (z.B. "input[type='text']")
            node_id: Root node ID (default: document root)
            
        Returns:
            nodeId oder None wenn nicht gefunden
        """
        if node_id is None:
            # Document holen
            doc = await self.get_document(session_id)
            node_id = doc.get("root", {}).get("nodeId")
        
        try:
            result = await self.send_to_session(session_id, "DOM.querySelector", {
                "nodeId": node_id,
                "selector": selector,
            })
            found_id = result.get("nodeId", 0)
            return found_id if found_id > 0 else None
        except Exception as e:
            logger.debug(f"querySelector fehlgeschlagen für '{selector}': {e}")
            return None

    async def get_box_model(self, session_id: str, node_id: int) -> Optional[Dict[str, Any]]:
        """
        Gibt die Bounding Box (Koordinaten) eines Elements zurück.
        
        Returns:
            {"content": [...], "padding": [...], "border": [...], "margin": [...]}
            oder None
        """
        try:
            result = await self.send_to_session(session_id, "DOM.getBoxModel", {"nodeId": node_id})
            return result.get("model")
        except Exception as e:
            logger.debug(f"getBoxModel fehlgeschlagen: {e}")
            return None

    async def focus_node(self, session_id: str, node_id: int):
        """Fokussiert ein DOM node."""
        await self.send_to_session(session_id, "DOM.focus", {"nodeId": node_id})

    async def set_node_value(self, session_id: str, node_id: int, value: str):
        """Setzt den Wert eines Input-Elements."""
        await self.send_to_session(session_id, "DOM.setNodeValue", {
            "nodeId": node_id,
            "value": value,
        })

    async def type_text(self, session_id: str, text: str):
        """
        Tippt Text über CDP Input.dispatchKeyEvents.
        
        WICHTIG: Dies simuliert echte Tastendrücke (nicht nur value setzen).
        Manche SPAs (wie GMX) reagieren nur auf key events, nicht auf value changes.
        """
        for char in text:
            await self.send_to_session(session_id, "Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": char,
            })
            await self.send_to_session(session_id, "Input.dispatchKeyEvent", {
                "type": "keyUp",
                "text": char,
            })


async def get_browser_ws_endpoint(cdp_port: int = 9222, timeout: float = 15.0) -> str:
    """
    Holt den Browser websocket endpoint vom CDP HTTP endpoint.
    
    Chrome's CDP hat zwei Endpoints:
    1. HTTP: http://127.0.0.1:9222/json/version  → gibt webSocketDebuggerUrl zurück
    2. Websocket: ws://127.0.0.1:9222/devtools/browser/...  → der eigentliche endpoint
    
    Args:
        cdp_port: Der remote-debugging-port
        timeout: Max wait time
        
    Returns:
        webSocketDebuggerUrl (z.B. "ws://127.0.0.1:9222/devtools/browser/...")
    """
    import aiohttp
    
    url = f"http://127.0.0.1:{cdp_port}/json/version"
    logger.info(f"Hole CDP endpoint von {url}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"CDP HTTP endpoint returned {resp.status}")
            data = await resp.json()
            ws_url = data.get("webSocketDebuggerUrl")
            if not ws_url:
                raise RuntimeError("Kein webSocketDebuggerUrl in CDP response")
            logger.info(f"CDP Endpoint gefunden: {ws_url[:50]}...")
            return ws_url


async def get_page_target(cdp_client: CDPClient, url_filter: str = "") -> Optional[Dict[str, Any]]:
    """
    Findet ein Page-Target (Tab) das eine bestimmte URL enthält.
    
    Args:
        cdp_client: Verbundener CDPClient
        url_filter: Substring der URL (z.B. "gmx.net")
        
    Returns:
        Target info dict oder None
    """
    targets = await cdp_client.get_targets()
    for target in targets:
        if target.get("type") == "page":
            if not url_filter or url_filter in target.get("url", ""):
                return target
    # Fallback: erstes page target
    for target in targets:
        if target.get("type") == "page":
            return target
    return None
