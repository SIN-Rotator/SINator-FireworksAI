#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         GMX ALIAS INTERACTION TOOL — READ-ONLY REFERENCE TOOL                ║
║                                                                              ║
║  ZWECK:                                                                      ║
║  Interaktives CLI-Tool für GMX Alias-Operationen. Verwendet die              ║
║  VERIFIZIERTEN GmxService-Methoden (KEINE EIGENE FLOW-LOGIK).                ║
║                                                                              ║
║  ⚠️ DIESES TOOL IST VERIFIZIERT — ÄNDERUNGEN VERBOTEN!                       ║
║  Einmal erstellt und getestet = READ-ONLY forever.                           ║
║  Wenn Bug: neuen Service schreiben, nicht dieses Tool ändern.                ║
║                                                                              ║
║  COMMANDS:                                                                   ║
║  python tools/gmx_alias_tool.py status           → GMX Session + Alias prüfen║
║  python tools/gmx_alias_tool.py rotate           → Alias rotieren (delete+new)║
║  python tools/gmx_alias_tool.py rotate <name>    → Alias mit bestimmtem Namen ║
║  python tools/gmx_alias_tool.py create <name>    → Nur Alias erstellen       ║
║  python tools/gmx_alias_tool.py delete           → Alias löschen             ║
║                                                                              ║
║  API ALTERNATIVE:                                                            ║
║  curl -X POST http://localhost:8000/gmx/alias/rotate                         ║
║  curl -X POST http://localhost:8000/gmx/alias/create?alias_name=<name>        ║
║  curl -X POST http://localhost:8000/gmx/session/check                         ║
║                                                                              ║
║  WICHTIG: Browser muss laufen! POST /browser/start zuerst.                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
Docs: gmx_alias_tool.doc.md
"""
import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_toolbox.core.gmx_service import GmxService


def print_result(label: str, result: dict):
    """Formatiert Ergebnis für CLI-Output."""
    status = result.get("status", "unknown")
    ok = status in ("success", "partial")
    
    status_icon = "✅" if ok else ("⚠️" if status == "partial" else "❌")
    
    print(f"\n{status_icon} {label}")
    print(f"   Status: {status}")
    
    if "created_alias" in result and result["created_alias"]:
        print(f"   Created: {result['created_alias']}")
    if "deleted_alias" in result and result["deleted_alias"]:
        print(f"   Deleted: {result['deleted_alias']}")
    if "alias_email" in result and result["alias_email"]:
        print(f"   Alias: {result['alias_email']}")
    
    if result.get("steps_completed"):
        print(f"   Steps OK: {' → '.join(result['steps_completed'])}")
    if result.get("steps_failed"):
        print(f"   Steps FAILED: {' → '.join(result['steps_failed'])}")
    
    if result.get("error"):
        print(f"   Error: {result['error']}")
    
    exec_time = result.get("execution_time", "N/A")
    print(f"   Time: {exec_time}")
    
    return ok


async def cmd_status():
    """Prüft GMX Session-Status und aktuellen Alias."""
    print("\n=== GMX Session Status ===")
    svc = GmxService()
    
    try:
        # Session check via create_alias (it does session validation internally)
        result = await svc.create_alias(alias_name=None, cdp_port=9222)
        
        if result.get("status") in ("success", "partial"):
            print("✅ GMX Session OK")
            if result.get("alias_email"):
                print(f"   Current Alias: {result['alias_email']}")
        elif result.get("status") == "not_logged_in":
            print("❌ GMX Session DEAD — Session Recovery nötig!")
            print("   → POST /cookies/inject um Session wiederherzustellen")
        else:
            print(f"❌ GMX Error: {result.get('error', 'unknown')}")
        
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        print("   Chrome läuft nicht? → POST /browser/start")


async def cmd_rotate(alias_name: str = None):
    """Alias rotieren: existierenden löschen + neuen erstellen."""
    print("\n=== GMX Alias Rotation ===")
    if alias_name:
        print(f"   Target: {alias_name}")
    else:
        print("   Target: AUTO-GENERATED")
    
    svc = GmxService()
    result = await svc.rotate_alias(new_alias_name=alias_name, cdp_port=9222)
    return print_result("Rotation", result)


async def cmd_create(alias_name: str = None):
    """Nur Alias erstellen (ohne Löschen)."""
    if alias_name:
        name = alias_name
    else:
        from agent_toolbox.core.gmx_service import GmxService as GmxSvcTemp
        svc_tmp = GmxSvcTemp()
        name = svc_tmp.generate_alias_name()
    
    print("\n=== GMX Alias Create ===")
    print(f"   Name: {name}")
    
    svc = GmxService()
    result = await svc.create_alias(alias_name=name, cdp_port=9222)
    return print_result("Create", result)


async def cmd_delete():
    """Alias löschen (mit Bestätigung)."""
    print("\n=== GMX Alias Delete ===")
    
    svc = GmxService()
    
    # First check what alias exists
    try:
        result = await svc.create_alias(alias_name=None, cdp_port=9222)
        current = result.get("alias_email") or "unbekannt"
        print(f"   Aktueller Alias: {current}")
    except:
        current = "unbekannt"
    
    confirm = input(f"   Alias '{current}' wirklich löschen? [y/N]: ")
    if confirm.strip().lower() != "y":
        print("   Abgebrochen.")
        return False
    
    delete_result = await svc.delete_existing_alias(cdp_port=9222)
    
    status = delete_result.get("status", "unknown")
    ok = status in ("success", "no_alias")
    
    status_icon = "✅" if ok else "❌"
    print(f"\n{status_icon} Delete")
    print(f"   Status: {status}")
    if delete_result.get("alias"):
        print(f"   Deleted: {delete_result['alias']}")
    if delete_result.get("error"):
        print(f"   Error: {delete_result['error']}")
    
    return ok


async def cmd_check():
    """Session-Validierung (GMX Homepage → E-Mail click → Inbox check)."""
    print("\n=== GMX Session Check ===")
    svc = GmxService()
    
    try:
        result = await svc.check_session(cdp_port=9222)
        
        status = result.get("status", "unknown")
        url = result.get("current_url", "")
        
        if status == "logged_in":
            print("✅ GMX Session ACTIVE")
            print(f"   URL: {url[:80]}")
            sid = result.get("sid", "")
            if sid:
                print(f"   SID: {sid[:20]}...")
        elif status == "not_logged_in":
            print("❌ GMX Session DEAD")
            print("   → Session Recovery nötig!")
        else:
            print(f"⚠️  GMX Status: {status}")
            print(f"   Error: {result.get('error', 'N/A')}")
        
        return status == "logged_in"
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="GMX Alias Interaction Tool (READ-ONLY VERIFIED)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status      GMX Session prüfen + aktuellen Alias anzeigen
  check       Detaillierte Session-Validierung
  rotate      Alias rotieren (delete + create, auto-generiert)
  rotate <N>  Alias rotieren mit bestimmtem Namen
  create      Nur Alias erstellen (auto-generiert)
  create <N>  Nur Alias erstellen mit bestimmtem Namen
  delete      Alias löschen (mit Bestätigung)

API Alternative:
  curl -X POST http://localhost:8000/gmx/alias/rotate
  curl -X POST http://localhost:8000/gmx/alias/create?alias_name=<name>
  curl -X POST http://localhost:8000/gmx/session/check

⚠️  READ-ONLY VERIFIED — ÄNDERN VERBOTEN!
        """
    )
    
    parser.add_argument("command", choices=["status", "check", "rotate", "create", "delete"], help="Command")
    parser.add_argument("name", nargs="?", default=None, help="Alias-Name (optional)")
    
    args = parser.parse_args()
    
    cmds = {
        "status": cmd_status,
        "check": cmd_check,
        "rotate": lambda: cmd_rotate(args.name),
        "create": lambda: cmd_create(args.name),
        "delete": cmd_delete,
    }
    
    ok = asyncio.run(cmds[args.command]())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()