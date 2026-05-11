#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║            OOPIF DIAGNOSE-TOOL — 3c.gmx.net Cross-Origin-Iframe              ║
║                                                                              ║
║  ZWECK                                                                       ║
║  ────                                                                        ║
║  Standalone-Diagnose für den OOPIF-Bug-Fix vom 2026-05-11.                   ║
║                                                                              ║
║  Tut NICHTS Destruktives. Klickt KEINE Buttons. Tippt KEINEN Text.           ║
║  Liest nur und druckt — damit man bei Problemen sofort sieht, an welcher    ║
║  Stelle die OOPIF-Pipeline bricht.                                           ║
║                                                                              ║
║  VORAUSSETZUNGEN                                                             ║
║  ───────────────                                                             ║
║   • Chrome läuft mit CDP-Port 9222 (Profile 901, wie üblich).                ║
║   • Du bist eingeloggt UND auf der E-Mail-Adressen-Settings-Seite,           ║
║     d.h. der 3c.gmx.net Iframe muss im Tab vorhanden sein.                   ║
║                                                                              ║
║  WAS GEPRÜFT WIRD (Reihenfolge wichtig — bei Bruch oben aufhören)            ║
║  ──────────────────────────────────────────────────────────────────          ║
║   [1] Target.getTargets liefert ein type="iframe" Target mit 3c.gmx.net      ║
║   [2] Target.attachToTarget(flatten=true) gibt eine eigene child sessionId   ║
║   [3] DOM.enable auf der child session funktioniert                          ║
║   [4] DOM.querySelector("iframe[src*='3c.gmx.net']") in der TOP-Session     ║
║       findet das <iframe>-Element                                            ║
║   [5] DOM.getBoxModel auf dem Iframe-Element liefert (x,y,w,h) > 0           ║
║   [6] DOM.performSearch("@gmx.de") in der CHILD-Session liefert > 0 Treffer ║
║   [7] DOM.getBoxModel auf einem Treffer-NodeId in CHILD-Session liefert      ║
║       iframe-LOKALE Koordinaten (typisch: x,y < 800, kleiner als Viewport)  ║
║   [8] oopif.to_top(local) ergibt eine Koordinate INNERHALB des Iframe-Box    ║
║                                                                              ║
║  USAGE                                                                       ║
║  ─────                                                                       ║
║      python tools/diagnose_oopif.py                                          ║
║      python tools/diagnose_oopif.py --cdp-port 9222                          ║
║      python tools/diagnose_oopif.py --search "Hinzufügen"                    ║
║      python tools/diagnose_oopif.py --verbose                                ║
║                                                                              ║
║  HISTORIE                                                                    ║
║  ───────                                                                     ║
║   2026-05-11  Eingeführt als Begleit-Tool zum OOPIF-Fix in cdp_client.py +  ║
║               gmx_service.py. Vorher klickte der Agent ins Leere mit         ║
║               hartcodierten (350,340) und hielt das für "verified".          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_toolbox.core.cdp_client import (
    CDPClient,
    OopifContext,
    get_browser_ws_endpoint,
    get_page_target,
)


# Farb-/Format-Helfer — bewusst minimal, keine externe Dependency.
def ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def info(msg: str) -> None:
    print(f"         {msg}")


def section(title: str) -> None:
    print(f"\n── {title} " + "─" * (76 - len(title)))


async def diagnose(cdp_port: int, search_query: str, verbose: bool) -> int:
    """
    Returns Exit-Code:
       0 = OOPIF voll funktional (alle 8 Stufen grün)
       1 = irgendwo gebrochen — Details in stdout
       2 = Chrome/CDP gar nicht erreichbar
    """
    print(f"OOPIF-Diagnose — cdp_port={cdp_port}, search='{search_query}'")
    section("[0] CDP Connect")
    try:
        ws_url = await get_browser_ws_endpoint(cdp_port=cdp_port)
    except Exception as e:
        fail(f"Kein Chrome auf Port {cdp_port}: {e}")
        return 2
    ok(f"Browser WS: {ws_url[:60]}...")

    client = CDPClient(ws_url)
    try:
        await client.connect()
        ok("CDP connected")

        # Page-Target finden (irgendeinen mail_settings Tab)
        page_target = await get_page_target(client, url_substring="mail_settings")
        if not page_target:
            page_target = await get_page_target(client, url_substring="gmx.")
        if not page_target:
            fail("Kein passender Page-Target (gmx.*) gefunden — bist du auf der GMX-Seite?")
            return 1
        top_session = await client.attach_to_target(page_target["targetId"])
        ok(f"Top-Session: target={page_target['targetId'][:12]}..., url={page_target.get('url','')[:70]}")

        # ── [1] Iframe-Target finden ─────────────────────────────────────
        section("[1] Iframe-Target via Target.getTargets")
        targets = await client.get_targets()
        iframe_targets = [t for t in targets if t.get("type") == "iframe"]
        info(f"Insgesamt {len(targets)} Targets, davon {len(iframe_targets)} iframe-Targets")
        if verbose:
            for t in iframe_targets:
                info(f"  · iframe: {t.get('url', '')[:90]}")
        iframe = await client.find_iframe_target("3c.gmx.net")
        if not iframe:
            fail("Kein iframe-Target mit URL-Substring '3c.gmx.net' gefunden")
            info("→ Bist du auf der E-Mail-Adressen-Settings-Seite? Iframe wird nur dort geladen.")
            return 1
        ok(f"3c.gmx.net iframe: targetId={iframe['targetId'][:12]}..., url={iframe.get('url','')[:80]}")

        # ── [2] Attach an iframe-Target ──────────────────────────────────
        section("[2] Target.attachToTarget(flatten=true)")
        attached = await client.attach_to_iframe("3c.gmx.net")
        if not attached:
            fail("attach_to_iframe lieferte None")
            return 1
        child_session, _ = attached
        ok(f"child_session={child_session[:12]}...")

        # ── [3] DOM.enable in child session ──────────────────────────────
        section("[3] DOM.enable in child_session")
        try:
            await client.send_to_session(child_session, "DOM.enable")
            ok("DOM.enable OK")
        except Exception as e:
            fail(f"DOM.enable fehlgeschlagen: {e}")
            return 1

        # ── [4] Iframe-Element in Parent-DOM finden ──────────────────────
        section("[4] DOM.querySelector('iframe[src*=\"3c.gmx.net\"]') in Top-Session")
        await client.send_to_session(top_session, "DOM.enable")
        doc = await client.send_to_session(top_session, "DOM.getDocument", {"depth": 1})
        root_id = doc.get("root", {}).get("nodeId")
        if not root_id:
            fail("DOM.getDocument liefert keinen root nodeId")
            return 1
        ok(f"top_session root nodeId={root_id}")

        qs = await client.send_to_session(top_session, "DOM.querySelector", {
            "nodeId": root_id, "selector": "iframe[src*='3c.gmx.net']",
        })
        iframe_node = qs.get("nodeId", 0)
        if not iframe_node:
            fail("Iframe-Element nicht im Top-DOM gefunden (Selektor: iframe[src*='3c.gmx.net'])")
            return 1
        ok(f"iframe element nodeId={iframe_node}")

        # ── [5] getBoxModel auf Iframe-Element ───────────────────────────
        section("[5] DOM.getBoxModel auf das <iframe>-Element")
        box_res = await client.send_to_session(top_session, "DOM.getBoxModel", {"nodeId": iframe_node})
        model = box_res.get("model")
        if not model:
            fail("getBoxModel lieferte kein model (display:none? noch nicht gelayoutet?)")
            return 1
        c = model["content"]
        iframe_x, iframe_y = c[0], c[1]
        iframe_w, iframe_h = c[2] - c[0], c[7] - c[1]
        if iframe_w < 50 or iframe_h < 50:
            fail(f"Iframe-Box absurd klein: {iframe_w}x{iframe_h} — vermutlich nicht sichtbar")
            return 1
        ok(f"Iframe-Box: ({iframe_x:.0f},{iframe_y:.0f}) {iframe_w:.0f}x{iframe_h:.0f}")

        # ── [6] performSearch in child session ───────────────────────────
        section(f"[6] DOM.performSearch('{search_query}') in CHILD-Session")
        node_ids = await client.dom_search(
            child_session, search_query, include_shadow=True, max_results=50
        )
        info(f"resultCount={len(node_ids)}")
        if not node_ids:
            fail(
                f"Keine Treffer für '{search_query}' im Iframe-DOM. "
                f"Das ist das exakte Symptom des alten Bugs (top-session Suche)."
            )
            info("→ Wenn du sicher bist dass der Text sichtbar ist: Iframe-DOM ist evtl. leer (Lazy-Render?).")
            return 1
        ok(f"{len(node_ids)} Treffer-NodeIds (z.B. {node_ids[:5]})")

        # ── [7] getBoxModel auf einen Treffer in child session ───────────
        section("[7] DOM.getBoxModel auf einen Treffer in CHILD-Session")
        first_valid = None
        for nid in node_ids[:20]:
            node = await client.node_describe(child_session, nid)
            if not node:
                continue
            val = (node.get('nodeValue', '') or '').strip()
            if not val or val.startswith('{'):
                continue
            box = await client.node_content_box(child_session, nid)
            if not box:
                continue
            lx, ly, w, h = box
            if w < 5 or h < 5:
                continue
            first_valid = (nid, val, lx, ly, w, h)
            break

        if not first_valid:
            fail("Kein Treffer mit getBoxModel-Erfolg + plausibler Box gefunden")
            return 1
        nid, val, lx, ly, w, h = first_valid
        ok(f"nodeId={nid} text='{val[:50]}'")
        ok(f"iframe-lokale Box: ({lx:.0f},{ly:.0f}) {w:.0f}x{h:.0f}")
        if lx > iframe_w + 200 or ly > iframe_h + 200:
            fail(
                f"Lokale Koords ({lx:.0f},{ly:.0f}) sind GRÖßER als die Iframe-Box "
                f"({iframe_w:.0f}x{iframe_h:.0f}) — etwas ist faul. "
                f"Vielleicht doch Top-Viewport-Koords?"
            )
            return 1

        # ── [8] to_top Transform ──────────────────────────────────────────
        section("[8] Top-Viewport-Transformation via OopifContext.to_top()")
        oopif = OopifContext(
            parent_session_id=top_session,
            child_session_id=child_session,
            offset_x=iframe_x,
            offset_y=iframe_y,
            width=iframe_w,
            height=iframe_h,
        )
        cx, cy = oopif.to_top(lx + w / 2, ly + h / 2)
        ok(f"Center top-viewport: ({cx:.0f},{cy:.0f})")
        if not oopif.contains(cx, cy):
            fail(
                f"Center ({cx:.0f},{cy:.0f}) liegt AUßERHALB des Iframe-Rechtecks "
                f"({iframe_x:.0f},{iframe_y:.0f},{iframe_w:.0f}x{iframe_h:.0f}). "
                f"Etwas in der Transformation ist falsch."
            )
            return 1
        ok("Center liegt im Iframe-Rechteck — Mouse-Event würde landen wo erwartet")

        print(
            "\n══════════════════════════════════════════════════════════════════════════════\n"
            "  ALLE STUFEN GRÜN — OOPIF-Pipeline ist intakt für 3c.gmx.net.\n"
            f"  Beispiel-Treffer '{val[:30]}' wäre via:\n"
            f"    Input.dispatchMouseEvent (auf top_session) bei ({cx:.0f},{cy:.0f})\n"
            "  klickbar.\n"
            "══════════════════════════════════════════════════════════════════════════════\n"
        )
        return 0

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="OOPIF-Diagnose für 3c.gmx.net Cross-Origin-Iframe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--cdp-port", type=int, default=9222, help="CDP-Debug-Port (default: 9222)")
    parser.add_argument(
        "--search", default="@gmx.de",
        help="Suchquery für Stufe [6]+[7] (default: '@gmx.de'). "
             "Zum Test der Button-Suche: --search 'Hinzufügen'",
    )
    parser.add_argument("--verbose", action="store_true", help="Mehr Detail-Output")
    args = parser.parse_args()
    code = asyncio.run(diagnose(args.cdp_port, args.search, args.verbose))
    sys.exit(code)


if __name__ == "__main__":
    main()
