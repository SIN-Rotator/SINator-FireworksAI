#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          GMX-SETTINGS DIAGNOSE-TOOL — Direct Navigation Approach             ║
║                                                                              ║
║  ZWECK                                                                       ║
║  ────                                                                        ║
║  Standalone-Diagnose für GMX Alias-Settings DOM-Operationen.                 ║
║                                                                              ║
║  Tut NICHTS Destruktives. Klickt KEINE Buttons. Tippt KEINEN Text.           ║
║  Liest nur und druckt — damit man bei Problemen sofort sieht, an welcher    ║
║  Stelle die Pipeline bricht.                                                 ║
║                                                                              ║
║  WICHTIG — ARCHITEKTUR-ÄNDERUNG 2026-05-11:                                  ║
║  ──────────────────────────────────────────                                  ║
║  Der alte OOPIF-Ansatz (Target.getTargets für iframe-Targets) funktioniert   ║
║  NICHT, weil Chrome die GMX-Iframes nicht als separate CDP-Targets isoliert. ║
║                                                                              ║
║  NEUER ANSATZ: Direkte Navigation zu bap.navigator.gmx.net/mail_settings    ║
║  Der "Iframe-Inhalt" wird zum Top-Frame — keine OOPIF-Auflösung nötig.       ║
║                                                                              ║
║  VORAUSSETZUNGEN                                                             ║
║  ───────────────                                                             ║
║   • Chrome läuft mit CDP-Port 9222 (Profile 901, wie üblich).                ║
║   • Du bist bei GMX eingeloggt (SID in URL oder Cookie).                     ║
║                                                                              ║
║  WAS GEPRÜFT WIRD                                                            ║
║  ────────────────                                                            ║
║   [0] CDP Connect                                                            ║
║   [1] SID aus URL extrahieren                                                ║
║   [2] Direkte Navigation zu mail_settings (falls nötig)                      ║
║   [3] DOM.enable                                                             ║
║   [4] DOM.getDocument                                                        ║
║   [5] DOM.performSearch für Suchtext                                         ║
║   [6] DOM.getBoxModel auf Treffer                                            ║
║   [7] Koordinaten-Plausibilität                                              ║
║                                                                              ║
║  USAGE                                                                       ║
║  ─────                                                                       ║
║      python tools/diagnose_oopif.py                                          ║
║      python tools/diagnose_oopif.py --cdp-port 9222                          ║
║      python tools/diagnose_oopif.py --search "Hinzufügen"                    ║
║      python tools/diagnose_oopif.py --search "E-Mail-Adressen"               ║
║      python tools/diagnose_oopif.py --verbose                                ║
║                                                                              ║
║  HISTORIE                                                                    ║
║  ───────                                                                     ║
║   2026-05-11  v1: OOPIF-Ansatz (fehlgeschlagen - Chrome isoliert nicht)     ║
║   2026-05-11  v2: Direct Navigation Ansatz (funktioniert)                    ║
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
       0 = OOPIF voll funktional (alle Stufen grün)
       1 = irgendwo gebrochen — Details in stdout
       2 = Chrome/CDP gar nicht erreichbar

    BUG-FIX 2026-05-11: Diagnose-Tool aktualisiert für DIRECT NAVIGATION Ansatz.
    GMX-Iframes erscheinen NICHT als CDP iframe-Targets (Chrome isoliert sie nicht).
    Stattdessen navigieren wir direkt zur Settings-URL und arbeiten auf dem Top-Frame.
    """
    print(f"GMX-Settings-Diagnose — cdp_port={cdp_port}, search='{search_query}'")
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

        # Page-Target finden (irgendeinen GMX Tab)
        page_target = await get_page_target(client, url_substring="mail_settings")
        if not page_target:
            page_target = await get_page_target(client, url_substring="gmx.")
        if not page_target:
            fail("Kein passender Page-Target (gmx.*) gefunden — bist du auf der GMX-Seite?")
            return 1
        top_session = await client.attach_to_target(page_target["targetId"])
        current_url = page_target.get('url', '')
        ok(f"Top-Session: target={page_target['targetId'][:12]}..., url={current_url[:70]}")

        # ── [1] SID extrahieren ──────────────────────────────────────────
        section("[1] SID aus URL extrahieren")
        import re
        sid_match = re.search(r'[?&]sid=([a-f0-9]{70,})', current_url)
        sid = sid_match.group(1) if sid_match else None
        if not sid:
            # Fallback: aus anderen Targets suchen
            targets = await client.get_targets()
            for t in targets:
                t_url = t.get("url", "")
                if t.get("type") == "page" and "gmx.net" in t_url:
                    m = re.search(r'[?&]sid=([a-f0-9]{70,})', t_url)
                    if m:
                        sid = m.group(1)
                        break
        if not sid:
            fail("Kein SID gefunden — nicht eingeloggt bei GMX?")
            return 1
        ok(f"SID gefunden: {sid[:20]}...")

        # ── [2] Direkte Navigation zu mail_settings ──────────────────────
        section("[2] Direkte Navigation zu mail_settings")
        if "mail_settings" not in current_url:
            settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
            info(f"Navigiere zu: {settings_url[:80]}")
            await client.navigate(top_session, settings_url)
            import asyncio
            await asyncio.sleep(4)
            # URL verifizieren
            url_result = await client.send_to_session(top_session, "Runtime.evaluate", {
                "expression": "window.location.href", "returnByValue": True
            })
            current_url = url_result.get("result", {}).get("value", "")
            if "mail_settings" not in current_url and "gmx.net" not in current_url:
                fail(f"Navigation fehlgeschlagen, URL ist: {current_url[:80]}")
                return 1
        ok(f"Auf Settings-Seite: {current_url[:70]}")

        # ── [3] DOM.enable ───────────────────────────────────────────────
        section("[3] DOM.enable")
        try:
            await client.send_to_session(top_session, "DOM.enable")
            ok("DOM.enable OK")
        except Exception as e:
            fail(f"DOM.enable fehlgeschlagen: {e}")
            return 1

        # ── [4] DOM.getDocument ──────────────────────────────────────────
        section("[4] DOM.getDocument")
        doc = await client.send_to_session(top_session, "DOM.getDocument", {"depth": 1})
        root_id = doc.get("root", {}).get("nodeId")
        if not root_id:
            fail("DOM.getDocument liefert keinen root nodeId")
            return 1
        ok(f"root nodeId={root_id}")

        # ── [5] performSearch ────────────────────────────────────────────
        section(f"[5] DOM.performSearch('{search_query}')")
        node_ids = await client.dom_search(
            top_session, search_query, include_shadow=True, max_results=50
        )
        info(f"resultCount={len(node_ids)}")
        if not node_ids:
            fail(f"Keine Treffer für '{search_query}' im DOM.")
            info("→ Seite könnte noch laden oder falscher Suchtext.")
            return 1
        ok(f"{len(node_ids)} Treffer-NodeIds (z.B. {node_ids[:5]})")

        # ── [6] getBoxModel auf einen Treffer ────────────────────────────
        section("[6] DOM.getBoxModel auf einen Treffer")
        first_valid = None
        for nid in node_ids[:20]:
            node = await client.node_describe(top_session, nid)
            if not node:
                continue
            val = (node.get('nodeValue', '') or '').strip()
            if not val or val.startswith('{'):
                continue
            box = await client.node_content_box(top_session, nid)
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
        ok(f"Box: ({lx:.0f},{ly:.0f}) {w:.0f}x{h:.0f}")

        # ── [7] Koordinaten-Plausibilität ────────────────────────────────
        section("[7] Koordinaten-Plausibilität")
        cx, cy = lx + w / 2, ly + h / 2
        if cx < 0 or cy < 0 or cx > 2000 or cy > 2000:
            fail(f"Center ({cx:.0f},{cy:.0f}) außerhalb plausibler Viewport-Grenzen")
            return 1
        ok(f"Center: ({cx:.0f},{cy:.0f}) — im sichtbaren Viewport")

        print(
            "\n══════════════════════════════════════════════════════════════════════════════\n"
            "  ALLE STUFEN GRÜN — Direct-Navigation-Ansatz funktioniert!\n"
            f"  Beispiel-Treffer '{val[:30]}' wäre via:\n"
            f"    Input.dispatchMouseEvent bei ({cx:.0f},{cy:.0f})\n"
            "  klickbar.\n"
            "\n"
            "  HINWEIS: Chrome isoliert GMX-Iframes NICHT als separate CDP-Targets.\n"
            "  Daher navigieren wir direkt zur Settings-URL und arbeiten auf dem Top-Frame.\n"
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
