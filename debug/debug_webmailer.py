#!/usr/bin/env python3
"""
Debug-Skript: GMX Webmailer DOM-Inspektion
Ziel: Verstehen wie man Emails im Shadow-DOM Webmailer klicken kann.
"""
import asyncio
import json
import re
import sys
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target
from agent_toolbox.core.gmx_service import GmxService

async def inspect_webmailer():
    svc = GmxService()
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    # 1. Ensure GMX session
    url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_result.get("result", {}).get("value", "")
    print(f"Current URL: {current_url}")

    sid = None
    if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
        sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
        sid = sid_match.group(1) if sid_match else None

    if not sid:
        sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
        sid = sid_match.group(1) if sid_match else None
        print(f"URL after nav: {current_url}")
        print(f"SID: {sid}")

    if not sid:
        print("No SID found!")
        await client.disconnect()
        return

    # 2. Navigate to mail page and extract iframe
    mail_url = f"https://bap.navigator.gmx.net/mail?sid={sid}"
    print(f"Navigating to mail page...")
    await client.navigate(session_id, mail_url)
    await asyncio.sleep(6)

    iframe_res = await client.evaluate(session_id, '''
    (function() {
        const iframe = document.querySelector("#thirdPartyFrame_mail");
        return iframe ? iframe.src : null;
    })()
    ''', return_by_value=True)
    iframe_src = iframe_res.get('result', {}).get('value', '')
    print(f"Iframe src: {iframe_src}")

    if not iframe_src:
        await client.disconnect()
        return

    # 3. Navigate to webmailer
    print("Navigating to webmailer...")
    await client.navigate(session_id, iframe_src)
    await asyncio.sleep(5)

    # Screenshot
    await client.screenshot(session_id, path="/tmp/webmailer_overview.png")
    print("Screenshot saved to /tmp/webmailer_overview.png")

    # 4. Dump custom elements and shadow roots
    dom_dump = await client.evaluate(session_id, '''
    (function() {
        const results = [];
        function walk(node, depth) {
            if (depth > 15) return;
            if (node.shadowRoot) {
                const tag = node.tagName.toLowerCase();
                const children = Array.from(node.shadowRoot.querySelectorAll("*")).map(e => e.tagName.toLowerCase());
                const uniqueChildren = [...new Set(children)].slice(0, 20);
                results.push({tag, depth, children: uniqueChildren, text: node.textContent.slice(0, 100)});
                // Also walk into shadow root children
                for (const child of node.shadowRoot.querySelectorAll("*")) {
                    walk(child, depth + 1);
                }
            }
            for (const child of node.children) {
                walk(child, depth);
            }
        }
        walk(document.body, 0);
        return results.slice(0, 50);
    })()
    ''', return_by_value=True)
    shadow_data = dom_dump.get('result', {}).get('value', [])
    print(f"\nShadow hosts found: {len(shadow_data)}")
    for item in shadow_data[:15]:
        print(f"  {item['tag']} (depth={item['depth']}): children={item['children']}, text={item['text'][:60]}")

    # 5. Find elements containing "fireworks" text, get their rects
    fireworks_elements = await client.evaluate(session_id, '''
    (function() {
        const matches = [];
        function walk(root, depth, path) {
            if (depth > 12) return;
            const all = root.querySelectorAll("*");
            for (const el of all) {
                const text = (el.textContent || "").toLowerCase();
                if (text.includes("fireworks") && el.getBoundingClientRect) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        matches.push({
                            tag: el.tagName.toLowerCase(),
                            path: path + ">" + el.tagName.toLowerCase(),
                            text: el.textContent.slice(0, 120).replace(/\\s+/g, " "),
                            rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                            hasShadow: !!el.shadowRoot,
                        });
                    }
                }
                if (el.shadowRoot) {
                    walk(el.shadowRoot, depth + 1, path + ">" + el.tagName.toLowerCase() + "::shadow");
                }
            }
        }
        walk(document.body, 0, "body");
        // Return top 10 by size (largest first, likely rows not tiny text spans)
        return matches.sort((a, b) => (b.rect.w * b.rect.h) - (a.rect.w * a.rect.h)).slice(0, 15);
    })()
    ''', return_by_value=True)
    fw_data = fireworks_elements.get('result', {}).get('value', [])
    print(f"\nElements containing 'fireworks' (top {len(fw_data)}):")
    for item in fw_data:
        print(f"  {item['tag']} | {item['rect']} | shadow={item['hasShadow']} | text={item['text'][:80]}")

    # 6. Try to find list-mail-item elements
    list_items = await client.evaluate(session_id, '''
    (function() {
        function walk(root, depth) {
            if (depth > 10) return [];
            let items = [];
            const all = root.querySelectorAll("*");
            for (const el of all) {
                const tag = el.tagName.toLowerCase();
                if (tag.startsWith("list-mail") || tag.startsWith("mail-list") || tag.startsWith("webmailer")) {
                    const rect = el.getBoundingClientRect();
                    items.push({
                        tag: tag,
                        rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                        text: el.textContent.slice(0, 100).replace(/\\s+/g, " "),
                    });
                }
                if (el.shadowRoot) {
                    items = items.concat(walk(el.shadowRoot, depth + 1));
                }
            }
            return items;
        }
        return walk(document.body, 0).slice(0, 20);
    })()
    ''', return_by_value=True)
    li_data = list_items.get('result', {}).get('value', [])
    print(f"\nCustom mail elements: {len(li_data)}")
    for item in li_data[:10]:
        print(f"  {item['tag']} | {item['rect']} | text={item['text'][:80]}")

    await client.disconnect()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(inspect_webmailer())
