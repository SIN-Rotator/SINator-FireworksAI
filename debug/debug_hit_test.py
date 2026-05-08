#!/usr/bin/env python3
"""
Debug-Skript: GMX Webmailer — pointer-events, iframes, event listeners
"""
import asyncio
import json
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def inspect_hit_test():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    await asyncio.sleep(2)

    # 1. Check pointer-events of list-mail-item and parents
    pe_res = await client.evaluate(session_id, '''
    (function() {
        function findItems(root) {
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item" && el.textContent.toLowerCase().includes("verify")) {
                    const style = window.getComputedStyle(el);
                    // Walk up parents and check styles
                    let parents = [];
                    let p = el.parentElement;
                    for (let i = 0; i < 8 && p; i++) {
                        const ps = window.getComputedStyle(p);
                        parents.push({
                            tag: p.tagName.toLowerCase(),
                            pointerEvents: ps.pointerEvents,
                            display: ps.display,
                            position: ps.position,
                            zIndex: ps.zIndex,
                            rect: (() => { const r = p.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })(),
                        });
                        p = p.parentElement;
                    }
                    return {
                        itemPE: style.pointerEvents,
                        itemDisplay: style.display,
                        itemPosition: style.position,
                        itemZIndex: style.zIndex,
                        itemRect: (() => { const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })(),
                        parents: parents,
                    };
                }
                if (el.shadowRoot) {
                    const res = findItems(el.shadowRoot);
                    if (res) return res;
                }
            }
            return null;
        }
        return findItems(document.body);
    })()
    ''', return_by_value=True)
    pe = pe_res.get('result', {}).get('value', {})
    print(f"list-mail-item styles:")
    print(f"  pointer-events: {pe.get('itemPE')}")
    print(f"  display: {pe.get('itemDisplay')}")
    print(f"  position: {pe.get('itemPosition')}")
    print(f"  z-index: {pe.get('itemZIndex')}")
    print(f"  rect: {pe.get('itemRect')}")
    print(f"  Parents (upward):")
    for p in pe.get('parents', []):
        print(f"    {p['tag']}: pe={p['pointerEvents']}, display={p['display']}, pos={p['position']}, z={p['zIndex']}, rect={p['rect']}")

    # 2. Check all iframes on the page
    iframe_res = await client.evaluate(session_id, '''
    (function() {
        const iframes = document.querySelectorAll("iframe");
        return Array.from(iframes).map(f => ({
            src: f.src,
            id: f.id,
            name: f.name,
            rect: (() => { const r = f.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })(),
        }));
    })()
    ''', return_by_value=True)
    iframes = iframe_res.get('result', {}).get('value', [])
    print(f"\nIframes on page: {len(iframes)}")
    for f in iframes:
        print(f"  {f.get('id')} src={f.get('src', '')[:80]} rect={f.get('rect')}")

    # 3. Check elementFromPoint at various positions within the item
    efp_res = await client.evaluate(session_id, '''
    (function() {
        function findItem(root) {
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item" && el.textContent.toLowerCase().includes("verify")) {
                    const r = el.getBoundingClientRect();
                    const points = [
                        {x: r.x + 10, y: r.y + r.height/2},
                        {x: r.x + r.width/2, y: r.y + r.height/2},
                        {x: r.x + r.width - 10, y: r.y + r.height/2},
                        {x: r.x + r.width/2, y: r.y + 10},
                        {x: r.x + r.width/2, y: r.y + r.height - 10},
                    ];
                    return points.map(pt => {
                        const e = document.elementFromPoint(pt.x, pt.y);
                        return {
                            pt: pt,
                            tag: e ? e.tagName.toLowerCase() : null,
                            text: e ? e.textContent.slice(0, 60) : null,
                        };
                    });
                }
                if (el.shadowRoot) {
                    const res = findItem(el.shadowRoot);
                    if (res) return res;
                }
            }
            return [];
        }
        return findItem(document.body);
    })()
    ''', return_by_value=True)
    points = efp_res.get('result', {}).get('value', [])
    print(f"\nelementFromPoint results:")
    for p in points:
        print(f"  ({p['pt']['x']}, {p['pt']['y']}) => {p['tag']} | text={p['text'][:50] if p['text'] else ''}")

    # 4. Check if there are any transparent overlays or canvases
    overlay_res = await client.evaluate(session_id, '''
    (function() {
        const all = document.querySelectorAll("*");
        let overlays = [];
        for (const el of all) {
            const style = window.getComputedStyle(el);
            if (style.pointerEvents !== "none" && style.opacity === "0" && el.getBoundingClientRect().width > 200) {
                overlays.push({tag: el.tagName.toLowerCase(), rect: (() => { const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })()});
            }
        }
        return overlays.slice(0, 10);
    })()
    ''', return_by_value=True)
    overlays = overlay_res.get('result', {}).get('value', [])
    print(f"\nTransparent overlays (opacity=0, pointerEvents!=none): {len(overlays)}")
    for o in overlays:
        print(f"  {o['tag']} rect={o['rect']}")

    # 5. Try using DOM.getNodeForLocation (CDP) to find what's at the point
    print(f"\nTrying CDP DOM.getNodeForLocation...")
    try:
        # First get document node id
        doc_res = await client.send_to_session(session_id, "DOM.getDocument")
        doc_node_id = doc_res.get("root", {}).get("nodeId")
        print(f"Document nodeId: {doc_node_id}")

        node_res = await client.send_to_session(session_id, "DOM.getNodeForLocation", {
            "x": 445, "y": 304, "includeUserAgentShadowDOM": True,
        })
        print(f"DOM.getNodeForLocation result: {json.dumps(node_res, indent=2)[:500]}")
    except Exception as e:
        print(f"CDP DOM.getNodeForLocation failed: {e}")

    await client.disconnect()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(inspect_hit_test())
