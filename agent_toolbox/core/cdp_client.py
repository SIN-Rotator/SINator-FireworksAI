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
║  OOPIF SUPPORT (Bug-Fix 2026-05-11):                                         ║
║  Für Cross-Origin-Iframes (3c.gmx.net) reicht eine einzige Top-Session       ║
║  NICHT — der Iframe lebt seit Chrome 67 (Site Isolation) in einem eigenen    ║
║  Renderer-Prozess mit eigener DOM-Agent-Session.                             ║
║                                                                              ║
║  Konsequenz für GMX-Alias-Flow:                                              ║
║    DOM.performSearch in Top-Session findet KEINE Iframe-Inhalte              ║
║    DOM.getBoxModel mit OOPIF-NodeIds → "Could not find node" / Müll          ║
║    Input.dispatchMouseEvent mit Iframe-lokalen Koords → klickt ins Leere     ║
║                                                                              ║
║  Lösung: `OopifContext` (siehe Klasse unten) + `CDPClient.resolve_oopif()`:  ║
║    1. Target.getTargets → iframe-Target finden (type="iframe", url-match)    ║
║    2. Target.attachToTarget(flatten=True) → eigene child_session_id          ║
║    3. DOM-Operationen in child_session_id → iframe-lokale Koords             ║
║    4. <iframe>-Element in Parent-Session → offset_x, offset_y                ║
║    5. top_coord = iframe_offset + iframe_local                               ║
║    6. Input.dispatchMouseEvent auf PARENT-Session mit top_coord              ║
║                                                                              ║
║  Anti-Pattern (was den Bug verursacht hat):                                  ║
║    DOM.performSearch + getBoxModel ALLES auf Top-Session und dann            ║
║    rohe Koordinaten an Input.dispatchMouseEvent → broken.                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
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
class CDPResponse:
    """Strukturierte CDP Response."""
    id: Optional[int]
    result: Optional[Dict[str, Any]]
    error: Optional[Dict[str, Any]]
    method: Optional[str]  # Für async events (notifications)
    params: Optional[Dict[str, Any]]


@dataclass
class OopifContext:
    """
    Out-Of-Process Iframe (OOPIF) Kontext für Cross-Origin-Iframes.

    ════════════════════════════════════════════════════════════════════════════
    HINTERGRUND — warum diese Klasse existiert (Bug-Report 2026-05-11):
    ════════════════════════════════════════════════════════════════════════════

    Seit Chrome 67 (Site Isolation, default-on) läuft jedes Cross-Origin-Iframe
    in einem EIGENEN Renderer-Prozess und hat ein EIGENES CDP-Target
    (type="iframe") mit EIGENER DOM-Agent-Session.

    Folgen für SINator (3c.gmx.net Iframe im bap.navigator.gmx.net Tab):

      1. `DOM.performSearch` auf der TOP-Session findet KEINE Inhalte im OOPIF
         → resultCount=0, oder es kommen Top-Frame-NodeIds die nichts mit dem
         gesuchten Iframe-Text zu tun haben.

      2. Selbst wenn man eine NodeId aus dem Iframe rät, ist sie in der
         Top-Session NICHT auflösbar → `DOM.getBoxModel` crasht mit
         "Could not find node" oder liefert undefined behavior.

      3. `Input.dispatchMouseEvent` läuft IMMER auf der TOP-Session und nutzt
         VIEWPORT-Koordinaten. Es gibt KEINE Möglichkeit, Mouse-Events direkt
         in eine OOPIF-Session zu schicken — sie gehen durchs Browserfenster
         und Chrome routet sie dann ins richtige Iframe basierend auf
         Viewport-Position.

    ════════════════════════════════════════════════════════════════════════════
    LÖSUNG (was diese Klasse macht):
    ════════════════════════════════════════════════════════════════════════════

    1. `child_session_id` ist eine separate CDP-Session, attached an das
       OOPIF-Target. Auf DIESER Session laufen `DOM.performSearch`,
       `DOM.describeNode`, `DOM.getBoxModel` korrekt — die zurückgegebenen
       Koordinaten sind IFRAME-LOKAL (Ursprung = top-left des Iframe-Inhalts).

    2. `parent_session_id` ist die TOP-Session (der Tab). Dort haben wir das
       `<iframe>` Element selbst gefunden und sein Viewport-Box geholt:
       (offset_x, offset_y, width, height).

    3. `to_top(local_x, local_y)` rechnet Iframe-lokale Koordinaten in
       Top-Viewport-Koordinaten um. Die transformierten Koordinaten gehen
       direkt an `Input.dispatchMouseEvent` auf der `parent_session_id` und
       treffen das Element exakt.

    ════════════════════════════════════════════════════════════════════════════
    SCROLLING & STALENESS:
    ════════════════════════════════════════════════════════════════════════════

    Wenn der PARENT scrollt, wandert das Iframe-Element im Viewport mit
    → offset_x/offset_y ändern sich → DIESEN CONTEXT NEU AUFLÖSEN vor jedem
    Klick (siehe `gmx_service._resolve_gmx_oopif`).

    Wenn INNERHALB des Iframe gescrollt wird, ändern sich die iframe-lokalen
    Koordinaten der Elemente — auch hier: immer FRISCH suchen, nicht cachen.

    NodeIds sind ebenfalls staleness-anfällig: nach jedem DOM-Update können
    sie ungültig werden. Konsequenz: pro Click neu searchen, niemals NodeIds
    zwischen verschiedenen High-Level-Operationen wiederverwenden.

    ════════════════════════════════════════════════════════════════════════════
    BEKANNTE FALLEN (gegen die wir hier verteidigen):
    ════════════════════════════════════════════════════════════════════════════

    • DOM.performSearch mit `includeUserAgentShadowDOM:true` durchsucht NICHT
      die DOM eines OOPIF — nur Shadow-DOM des aktuellen Prozesses.
    • Target.getTargets liefert die OOPIF-Targets als type="iframe".
      Target.attachToTarget mit `flatten:true` liefert die kindliche sessionId.
    • DOM-Agent muss in der child-session EXPLIZIT enabled werden (DOM.enable)
      bevor performSearch/getBoxModel funktionieren.
    """
    parent_session_id: str
    child_session_id: str
    offset_x: float
    offset_y: float
    width: float
    height: float
    target_id: str = ""
    iframe_url: str = ""

    def to_top(self, local_x: float, local_y: float) -> Tuple[float, float]:
        """
        Wandelt iframe-lokale Koordinaten (aus `DOM.getBoxModel` der
        child_session) in Top-Viewport-Koordinaten um, die für
        `Input.dispatchMouseEvent` auf der parent_session brauchbar sind.

        Formel: top = iframe_viewport_offset + iframe_local
        """
        return (self.offset_x + local_x, self.offset_y + local_y)

    def contains(self, top_x: float, top_y: float) -> bool:
        """Sanity-Check: liegt eine Top-Viewport-Koordinate im Iframe-Rechteck?"""
        return (
            self.offset_x <= top_x <= self.offset_x + self.width
            and self.offset_y <= top_y <= self.offset_y + self.height
        )


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

    # ═══════════════════════════════════════════════════════════════════════════════
    #  OOPIF (Out-Of-Process-Iframe / Cross-Origin-Iframe) SUPPORT
    #  ────────────────────────────────────────────────────────────────────────────
    #  Eingeführt 2026-05-11 als Bug-Fix für gmx_service.py:
    #    - DOM.getBoxModel crasht mit stale/null NodeIds für 3c.gmx.net Inhalte
    #    - Input.dispatchMouseEvent mit hartcodierten (350,340) klickt ins Leere
    #  Ursache: 3c.gmx.net läuft in eigenem Renderer-Prozess (Site Isolation).
    #  Lösung: separate CDP-Session pro OOPIF + Viewport-Offset-Transformation.
    #  Siehe Klasse OopifContext oben für die volle Hintergrund-Doku.
    # ═══════════════════════════════════════════════════════════════════════════════

    async def find_iframe_target(self, url_substring: str) -> Optional[Dict[str, Any]]:
        """
        Findet ein OOPIF-Target anhand eines URL-Substrings.

        Chrome listet jedes Cross-Origin-Iframe als eigenes Target mit
        type="iframe" in `Target.getTargets`. Dieser Helfer durchsucht alle
        Targets nach dem ersten iframe-Target, dessen URL den gegebenen
        Substring enthält.

        Args:
            url_substring: z.B. "3c.gmx.net"

        Returns:
            target info dict mit targetId, type, url — oder None falls kein
            passendes Iframe-Target offen ist (z.B. weil die Seite die das
            Iframe enthält noch nicht geladen wurde).
        """
        targets = await self.get_targets()
        for t in targets:
            if t.get("type") == "iframe" and url_substring in t.get("url", ""):
                return t
        return None

    async def attach_to_iframe(self, url_substring: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Findet ein OOPIF-Target via URL-Substring und attached daran.

        Returns:
            (child_session_id, target_info) oder None.
            Die child_session ist sofort nutzbar für `send_to_session`.
            DOM.enable wird hier NICHT automatisch gerufen — das macht der
            Caller, weil manche Operationen DOM gar nicht brauchen.
        """
        target = await self.find_iframe_target(url_substring)
        if not target:
            logger.warning(f"Kein Iframe-Target gefunden mit URL-Substring '{url_substring}'")
            return None
        session_id = await self.attach_to_target(target["targetId"])
        logger.info(
            f"OOPIF attached: target={target['targetId'][:12]}..., "
            f"session={session_id[:12]}..., url={target.get('url', '')[:60]}"
        )
        return session_id, target

    async def get_iframe_viewport_box(
        self, parent_session_id: str, iframe_selector: str
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Liefert (x, y, width, height) des Iframe-Elements im Parent-Viewport.

        Diese Werte sind der OFFSET, den man auf iframe-lokale Koordinaten
        (aus der child-session) draufaddieren muss, um Top-Viewport-Koordinaten
        zu bekommen — die `Input.dispatchMouseEvent` versteht.

        Args:
            parent_session_id: Session des Tabs (Top-Session)
            iframe_selector: CSS-Selektor für das <iframe> Element im Parent-DOM,
                             z.B. "iframe[src*='3c.gmx.net']"

        Returns:
            (x, y, w, h) oder None falls Iframe-Element nicht gefunden bzw.
            getBoxModel fehlschlägt (z.B. display:none).

        Hinweis: getBoxModel kann fehlschlagen wenn das Iframe noch nicht
        gelayoutet ist. Caller sollte retry mit kurzer Wartezeit.
        """
        try:
            doc = await self.send_to_session(parent_session_id, "DOM.getDocument", {"depth": 1})
            root_id = doc.get("root", {}).get("nodeId")
            if not root_id:
                logger.warning("get_iframe_viewport_box: kein root nodeId in DOM.getDocument")
                return None
            qs = await self.send_to_session(parent_session_id, "DOM.querySelector", {
                "nodeId": root_id, "selector": iframe_selector,
            })
            iframe_node = qs.get("nodeId", 0)
            if not iframe_node:
                logger.warning(f"get_iframe_viewport_box: Iframe '{iframe_selector}' nicht gefunden")
                return None
            box_res = await self.send_to_session(parent_session_id, "DOM.getBoxModel", {
                "nodeId": iframe_node,
            })
            model = box_res.get("model")
            if not model:
                return None
            # content array: [x1,y1, x2,y1, x2,y2, x1,y2] (4 Eckpunkte, 8 Werte)
            c = model["content"]
            x = c[0]
            y = c[1]
            w = c[2] - c[0]
            h = c[7] - c[1]
            return (x, y, w, h)
        except Exception as e:
            logger.debug(f"get_iframe_viewport_box fehlgeschlagen: {e}")
            return None

    async def resolve_oopif(
        self,
        parent_session_id: str,
        url_substring: str,
        iframe_selector: str,
        enable_dom: bool = True,
    ) -> Optional[OopifContext]:
        """
        End-to-end OOPIF-Auflösung: Iframe-Target finden + attach + Offset holen.

        Diese Methode bündelt die drei Schritte, die für jede koordinaten-basierte
        Operation in einem Cross-Origin-Iframe nötig sind:

          1. Iframe-Target finden (Target.getTargets, type=iframe, url-match)
          2. Attach (Target.attachToTarget, flatten=True) → child_session_id
          3. Iframe-Element-Box im Parent-Viewport bestimmen → offset_x, offset_y

        Args:
            parent_session_id: Session des Tabs (Top-Session)
            url_substring: z.B. "3c.gmx.net" — für Target-Match
            iframe_selector: CSS-Selektor für das <iframe>-Element im Parent-DOM,
                             z.B. "iframe[src*='3c.gmx.net']"
            enable_dom: Wenn True, wird DOM.enable auf der child_session gerufen
                        (Voraussetzung für performSearch/getBoxModel im Iframe).

        Returns:
            OopifContext oder None.

        ACHTUNG: NodeIds und Offsets sind staleness-anfällig. Diese Methode
        muss vor jeder neuen koordinaten-basierten Operation neu gerufen werden,
        wenn zwischendurch gescrollt/navigiert/UI-geupdated wurde.
        """
        attached = await self.attach_to_iframe(url_substring)
        if not attached:
            return None
        child_session_id, target = attached

        if enable_dom:
            try:
                await self.send_to_session(child_session_id, "DOM.enable")
            except Exception as e:
                logger.warning(f"DOM.enable auf child session fehlgeschlagen: {e}")

        # Iframe-Element-Box im Parent-Viewport
        box = await self.get_iframe_viewport_box(parent_session_id, iframe_selector)
        if not box:
            # Kurz warten und nochmal versuchen (Iframe könnte noch im Layout sein)
            await asyncio.sleep(0.5)
            box = await self.get_iframe_viewport_box(parent_session_id, iframe_selector)
        if not box:
            logger.warning(
                f"resolve_oopif: child session ok, aber Iframe-Box "
                f"({iframe_selector}) nicht ermittelbar"
            )
            return None
        x, y, w, h = box

        return OopifContext(
            parent_session_id=parent_session_id,
            child_session_id=child_session_id,
            offset_x=x,
            offset_y=y,
            width=w,
            height=h,
            target_id=target.get("targetId", ""),
            iframe_url=target.get("url", ""),
        )

    async def dom_search(
        self, session_id: str, query: str, include_shadow: bool = True, max_results: int = 100
    ) -> List[int]:
        """
        Komfort-Wrapper um DOM.performSearch + DOM.getSearchResults.

        Liefert eine Liste von nodeIds, die im DOM-Tree der GEGEBENEN Session
        gültig sind. Aufrufer muss die Session richtig wählen:
          - Top-Session  → Suche im Top-Frame-DOM
          - Child-Session (OOPIF) → Suche im Iframe-DOM

        Args:
            session_id: CDP Session ID (Top oder Child)
            query: Suchtext (DOM.performSearch akzeptiert Text, CSS-Selectoren,
                   XPath — siehe CDP-Doku)
            include_shadow: Auch User-Agent-Shadow-DOM mit durchsuchen
            max_results: Obergrenze für zurückgegebene NodeIds

        Returns:
            Liste von nodeIds (kann leer sein).
        """
        try:
            search = await self.send_to_session(session_id, "DOM.performSearch", {
                "query": query,
                "includeUserAgentShadowDOM": include_shadow,
            })
        except Exception as e:
            logger.debug(f"DOM.performSearch fehlgeschlagen für '{query}': {e}")
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
        except Exception as e:
            logger.debug(f"DOM.getSearchResults fehlgeschlagen: {e}")
            return []

    async def node_content_box(
        self, session_id: str, node_id: int
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Liefert das Content-Box (x, y, w, h) eines Node in seinem session-eigenen
        Koordinaten-System.

        WICHTIG: Für Nodes aus einer Child-Session (OOPIF) sind diese Koordinaten
        IFRAME-LOKAL. Vor Input.dispatchMouseEvent über `OopifContext.to_top()`
        transformieren.

        Returns:
            (x, y, w, h) oder None bei Fehler / nicht-renderten Nodes.
        """
        try:
            res = await self.send_to_session(session_id, "DOM.getBoxModel", {"nodeId": node_id})
            model = res.get("model")
            if not model:
                return None
            c = model["content"]
            return (c[0], c[1], c[2] - c[0], c[7] - c[1])
        except Exception as e:
            logger.debug(f"node_content_box fehlgeschlagen für nodeId={node_id}: {e}")
            return None

    async def node_describe(
        self, session_id: str, node_id: int, depth: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Wrapper um DOM.describeNode, liefert das `node` Dict direkt (oder None).
        """
        try:
            res = await self.send_to_session(session_id, "DOM.describeNode", {
                "nodeId": node_id, "depth": depth,
            })
            return res.get("node")
        except Exception as e:
            logger.debug(f"describeNode fehlgeschlagen für nodeId={node_id}: {e}")
            return None

    @staticmethod
    def node_attrs_to_dict(node: Dict[str, Any]) -> Dict[str, str]:
        """
        Hilfsfunktion: die `attributes` Liste aus DOM.describeNode ist
        ['name1','val1','name2','val2',...] — hier in dict konvertiert.
        """
        attrs = node.get("attributes", []) or []
        d: Dict[str, str] = {}
        for j in range(0, len(attrs) - 1, 2):
            d[attrs[j]] = attrs[j + 1]
        return d


async def get_browser_ws_endpoint(cdp_port: int = 9222, timeout: float = 15.0) -> str:
    """
    Holt den Browser websocket endpoint vom CDP HTTP endpoint via urllib.
    
    Nutzt urllib (Standard Library) statt aiohttp für Zuverlässigkeit.
    """
    import urllib.request
    
    url = f"http://127.0.0.1:{cdp_port}/json/version"
    logger.info(f"Hole CDP endpoint von {url}")
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Python/CDP"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read()
        import json
        d = json.loads(data)
        ws_url = d.get("webSocketDebuggerUrl")
        if ws_url:
            logger.info(f"CDP Endpoint gefunden: {ws_url[:60]}...")
            return ws_url
    except Exception as e:
        logger.error(f"CDP endpoint fehlgeschlagen: {e}")
    
    raise RuntimeError(f"Chrome DevTools nicht erreichbar auf Port {cdp_port}")


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
    
    # Collect all matching page targets
    matching = []
    for target in targets:
        if target.get("type") == "page":
            if not url_filter or url_filter in target.get("url", ""):
                matching.append(target)
    
    # Prefer www.gmx.net over auth.gmx.net (auth.gmx.net has no ACCOUNT-AVATAR)
    non_auth = [t for t in matching if "auth.gmx.net" not in t.get("url", "")]
    if non_auth:
        # Prefer root URL over hash URL (hash URL = SPA hash route, root URL = page entry point)
        root = [t for t in non_auth if t.get("url", "").rstrip("/") == "https://www.gmx.net" or t.get("url", "").rstrip("/") == "http://www.gmx.net"]
        if root:
            return root[0]
        return non_auth[0]
    
    # Fallback: first matching target (may be auth.gmx.net)
    if matching:
        return matching[0]
    
    # Last resort: first page target
    for target in targets:
        if target.get("type") == "page":
            return target
    return None
