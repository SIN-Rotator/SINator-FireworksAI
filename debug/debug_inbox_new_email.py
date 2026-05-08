#!/usr/bin/env python3
"""
╦═══════════════════════════════════════════════════════════════════════════════╦
║  DEBUG: GMX Webmailer Inbox Inspektor                                          ║
║  ZWECK: Prüfen ob neue Fireworks Verify-Email für neuen Alias angekommen ist   ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  WARUM DIESES SKRIPT?                                                           ║
║  • Nach Rotation alpha-panther-870@gmx.de + Fireworks Registrierung           ║
║    kam keine neue Verify-Email in der Inbox an.                                ║
║  • Mögliche Ursachen: Spam-Ordner, Alias-Weiterleitung defekt,                 ║
║    Fireworks hat keine Email gesendet, Zustellungsverzögerung.                 ║
║  • Dieses Skript listet die neuesten 20 Emails mit Timestamps und prüft       ║
║    ob eine Email für den neuen Alias existiert.                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""
import asyncio
import re
import json
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def inspect_inbox_for_new_email():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    # Prüfe ob wir auf Webmailer sind, sonst navigiere dorthin
    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_res.get('result', {}).get('value', '')
    print(f"Aktuelle URL: {current_url[:120]}")

    if "3c-bap.gmx.net" not in current_url and "webmailer.gmx.net" not in current_url:
        print("Navigiere zu GMX Homepage...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        click_res = await client.evaluate(session_id, '''
        (function(){
            const els = Array.from(document.querySelectorAll("a, button, nav a"));
            const emailEl = els.find(e => (e.textContent||"").trim() === "E-Mail");
            if (emailEl) { emailEl.click(); return true; }
            return false;
        })()
        ''', return_by_value=True)
        print(f"E-Mail Navigation geklickt: {click_res}")
        await asyncio.sleep(5)
        url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        current_url = url_res.get('result', {}).get('value', '')
        sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
        sid = sid_match.group(1) if sid_match else None
        if sid:
            mail_url = f"https://bap.navigator.gmx.net/mail?sid={sid}"
            await client.navigate(session_id, mail_url)
            await asyncio.sleep(6)
            iframe_res = await client.evaluate(session_id, '''
            (function() {
                const iframe = document.querySelector("#thirdPartyFrame_mail");
                return iframe ? iframe.src : null;
            })()
            ''', return_by_value=True)
            iframe_src = iframe_res.get('result', {}).get('value', '')
            if iframe_src:
                await client.navigate(session_id, iframe_src)
                await asyncio.sleep(8)

    # Extrahiere die neuesten 20 list-mail-item Elemente mit allen Details
    items_res = await client.evaluate(session_id, '''
    (function() {
        function findItems(root, depth) {
            if (depth > 10) return [];
            let items = [];
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item") {
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 0) {
                        const idAttr = el.getAttribute("id");
                        const mailId = idAttr ? idAttr.replace(/^id/, "") : null;
                        items.push({
                            mailId: mailId,
                            text: el.textContent.trim().slice(0, 200).replace(/\\s+/g, " "),
                            rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                        });
                    }
                }
                if (el.shadowRoot) {
                    items = items.concat(findItems(el.shadowRoot, depth + 1));
                }
            }
            return items;
        }
        return findItems(document.body, 0).slice(0, 20);
    })()
    ''', return_by_value=True)
    items = items_res.get('result', {}).get('value', [])
    
    print(f"\n{'='*80}")
    print(f"INBOX: {len(items)} list-mail-item Elemente gefunden (Top 20)")
    print(f"{'='*80}")
    for i, item in enumerate(items):
        print(f"\n[{i}] mailId={item.get('mailId')}")
        print(f"     text={item.get('text', '')[:120]}")
        # Heuristische Erkennung
        text_lower = item.get('text', '').lower()
        if "fireworks" in text_lower and "verify" in text_lower:
            print(f"     🔴 VERIFIZIERUNGS-EMAIL (Fireworks)")
        elif "fireworks" in text_lower and "welcome" in text_lower:
            print(f"     🟢 WILLKOMMENS-EMAIL (Fireworks)")
        elif "fireworks" in text_lower:
            print(f"     🟡 FIREWORKS EMAIL (unbekannter Typ)")

    # Prüfe auf neuen Alias alpha-panther-870
    alias_check = await client.evaluate(session_id, '''
    (function() {
        const body = document.body.innerText;
        return {
            hasAlphaPanther: body.includes("alpha-panther-870"),
            hasFireworksVerify: body.includes("Verify your Fireworks account"),
            hasFireworksWelcome: body.includes("Welcome to Fireworks"),
        };
    })()
    ''', return_by_value=True)
    check = alias_check.get('result', {}).get('value', {})
    print(f"\n{'='*80}")
    print(f"SPEZIFISCHE SUCHE:")
    print(f"  alpha-panther-870 in Inbox: {check.get('hasAlphaPanther')}")
    print(f"  'Verify your Fireworks account' in Inbox: {check.get('hasFireworksVerify')}")
    print(f"  'Welcome to Fireworks' in Inbox: {check.get('hasFireworksWelcome')}")
    print(f"{'='*80}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(inspect_inbox_for_new_email())
