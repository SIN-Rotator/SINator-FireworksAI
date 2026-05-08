#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════════════
  FIREWORKS VERIFY-EMAIL DELIVERY INVESTIGATION
═══════════════════════════════════════════════════════════════════════════════════════

  ZUSTAND (2026-05-08):
  • Alias alpha-panther-870@gmx.de wurde erfolgreich erstellt (Step 1 OK)
  • Fireworks Account wurde erfolgreich registriert (Step 2 OK)
  • ABER: Keine neue Verify-Email ist in der GMX Inbox angekommen
  • Die neuesten Emails sind von 19:07/19:06 (vor der Rotation)

  HYPOTHESEN:
  H1: Fireworks hat den Account erkannt als "bereits existent" und keine
      Verify-Email gesendet, weil der Account in einer früheren Rotation
      bereits verifiziert wurde (Cookie/Super-Cookie Tracking).
  H2: Die Email wurde von GMX als Spam blockiert / in Spam-Ordner verschoben.
  H3: Fireworks hat KEINE Verify-Email gesendet (vielleicht weil die Email
      Adresse als "bounced" markiert ist oder API-Rate-Limits greifen).
  H4: Die Zustellung ist extrem verzögert (> 10 Minuten).

  TESTSTRATEGIE:
  1. Prüfe Spam-Ordner via API (tmai{mailId} für Spam-Ordner?)
  2. Versuche Fireworks Login mit alpha-panther-870@gmx.de + Passwort
     → Wenn Login funktioniert, existiert der Account bereits
     → Wenn Login fehlschlägt, wurde kein Account erstellt
  3. Prüfe Fireworks Dashboard direkt nach Login ob der Account
     bereits "verified" ist (kein "Please verify your email" Banner)
═══════════════════════════════════════════════════════════════════════════════════════
"""
import asyncio
import time
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target
from agent_toolbox.core.fireworks_service import get_fireworks_service

async def investigate():
    fw = get_fireworks_service()
    password = "SinatorTest2024!"
    email = "alpha-panther-870@gmx.de"
    cdp_port = 9222

    # ═══════════════════════════════════════════════════════════════════════
    # TEST 1: Fireworks Login mit neuem Alias
    # ═══════════════════════════════════════════════════════════════════════
    print("═" * 80)
    print("TEST 1: Fireworks Login mit alpha-panther-870@gmx.de")
    print("═" * 80)
    # _perform_login ist eine interne Methode die CDPClient + session_id braucht.
    # Wir verbinden uns kurz und rufen sie auf.
    ws_url = await get_browser_ws_endpoint(cdp_port)
    client = CDPClient(ws_url)
    await client.connect()
    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")
    login_result = await fw._perform_login(client=client, session_id=session_id, email=email, password=password)
    await client.disconnect()
    print(f"Login Ergebnis: {login_result}")

    # ═══════════════════════════════════════════════════════════════════════
    # TEST 2: Prüfe Dashboard nach Login
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 80)
    print("TEST 2: Fireworks Dashboard nach Login")
    print("═" * 80)
    ws_url = await get_browser_ws_endpoint(cdp_port)
    client = CDPClient(ws_url)
    await client.connect()
    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    await client.navigate(session_id, "https://app.fireworks.ai/dashboard")
    await asyncio.sleep(5)

    # Suche nach "verify" oder "confirm" Bannern im Dashboard
    verify_check = await client.evaluate(session_id, '''
    (function() {
        const text = document.body.innerText.toLowerCase();
        return {
            hasVerifyBanner: text.includes("verify your email") || text.includes("bestätigen") || text.includes("confirm"),
            hasWelcome: text.includes("welcome") || text.includes("dashboard") || text.includes("api key"),
            hasLoginForm: !!document.querySelector('input[type="email"]'),
            currentUrl: window.location.href,
        };
    })()
    ''', return_by_value=True)
    check = verify_check.get('result', {}).get('value', {})
    print(f"Dashboard Status: {json.dumps(check, indent=2)}")

    await client.disconnect()

    # ═══════════════════════════════════════════════════════════════════════
    # TEST 3: Re-Registrierung versuchen
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 80)
    print("TEST 3: Re-Registrierung mit alpha-panther-870@gmx.de")
    print("═" * 80)
    reg_result = await fw.register(email=email, password=password, cdp_port=cdp_port)
    print(f"Re-Registration Ergebnis: {reg_result}")

if __name__ == "__main__":
    import json
    asyncio.run(investigate())
