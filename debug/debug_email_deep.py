#!/usr/bin/env python3
"""
Debug-Skript: GMX Webmailer Email-Deep-Dive
Untersucht list-mail-item Attribute, Methoden, Event-Listener und Network-Requests.
"""
import asyncio
import json
import re
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def deep_inspect():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")
    await client.send_to_session(session_id, "Network.enable")

    await asyncio.sleep(2)

    # 1. Inspect ALL attributes of a list-mail-item
    attr_res = await client.evaluate(session_id, '''
    (function() {
        const el = document.querySelector("list-mail-item");
        if (!el) return {error: "no list-mail-item found"};
        const attrs = {};
        for (const attr of el.attributes) {
            attrs[attr.name] = attr.value.slice(0, 100);
        }
        // Also get all properties
        const props = {};
        const keys = Object.keys(el);
        for (const k of keys.slice(0, 30)) {
            try {
                const v = el[k];
                if (typeof v !== "object" && typeof v !== "function") {
                    props[k] = String(v).slice(0, 100);
                }
            } catch(e) {}
        }
        // Check prototype methods
        const proto = Object.getPrototypeOf(el);
        const methods = Object.getOwnPropertyNames(proto).filter(n => typeof proto[n] === "function").slice(0, 30);
        return {tagName: el.tagName, attrs, props, methods, text: el.textContent.slice(0, 80)};
    })()
    ''', return_by_value=True)
    info = attr_res.get('result', {}).get('value', {})
    print(f"First list-mail-item info:")
    print(f"  tagName: {info.get('tagName')}")
    print(f"  text: {info.get('text')}")
    print(f"  attrs: {json.dumps(info.get('attrs', {}), indent=2)}")
    print(f"  props: {json.dumps(info.get('props', {}), indent=2)}")
    print(f"  methods: {info.get('methods', [])}")

    # 2. Try calling various methods on a verify-email item
    methods_to_try = ["select", "open", "activate", "focus", "click", "expand", "show", "toggle"]
    for method in methods_to_try:
        try_res = await client.evaluate(session_id, f'''
        (function() {{
            const items = document.querySelectorAll("list-mail-item");
            for (const el of items) {{
                if (el.textContent.toLowerCase().includes("verify")) {{
                    if (typeof el.{method} === "function") {{
                        try {{ el.{method}(); return "{method}: called"; }} catch(e) {{ return "{method}: error " + e.message; }}
                    }}
                    return "{method}: not a function";
                }}
            }}
            return "verify item not found";
        }})()
        ''', return_by_value=True)
        print(f"  {try_res.get('result', {}).get('value', '')}")

    # 3. Look for any mail-id in the page source / data attributes
    id_res = await client.evaluate(session_id, '''
    (function() {
        const items = document.querySelectorAll("list-mail-item");
        return Array.from(items).slice(0, 5).map(el => {
            const data = {};
            for (const key of Object.keys(el.dataset || {})) {
                data[key] = el.dataset[key];
            }
            return {
                tagName: el.tagName,
                allAttrs: Array.from(el.attributes).map(a => ({name: a.name, value: a.value.slice(0, 60)})),
                dataset: data,
            };
        });
    })()
    ''', return_by_value=True)
    ids = id_res.get('result', {}).get('value', [])
    print(f"\nFirst 5 list-mail-item attributes:")
    for item in ids:
        print(f"  {item['tagName']}:")
        for a in item['allAttrs']:
            print(f"    {a['name']} = {a['value']}")
        if item['dataset']:
            print(f"    dataset: {json.dumps(item['dataset'])}")

    # 4. Check if there are any <a> tags or hrefs associated with list items
    link_res = await client.evaluate(session_id, '''
    (function() {
        const items = document.querySelectorAll("list-mail-item");
        let links = [];
        for (const el of items) {
            if (el.textContent.toLowerCase().includes("verify")) {
                const anchors = el.querySelectorAll("a[href]");
                for (const a of anchors) {
                    links.push({href: a.href, text: a.textContent.slice(0, 40)});
                }
                // Also check shadow root
                if (el.shadowRoot) {
                    const sa = el.shadowRoot.querySelectorAll("a[href]");
                    for (const a of sa) {
                        links.push({href: a.href, text: a.textContent.slice(0, 40), inShadow: true});
                    }
                }
            }
        }
        return links.slice(0, 10);
    })()
    ''', return_by_value=True)
    links = link_res.get('result', {}).get('value', [])
    print(f"\nLinks inside verify emails: {len(links)}")
    for l in links:
        print(f"  href={l.get('href')} text={l.get('text')} shadow={l.get('inShadow')}")

    # 5. Check for any click handlers using CDP DOMDebugger
    # First get the nodeId of a list-mail-item
    node_res = await client.evaluate(session_id, '''
    (function() {
        const el = document.querySelector("list-mail-item");
        return el ? {found: true} : {found: false};
    })()
    ''', return_by_value=True)
    print(f"\nlist-mail-item found for DOMDebugger: {node_res.get('result', {}).get('value', {})}")

    await client.disconnect()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(deep_inspect())
