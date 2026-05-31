#!/usr/bin/env python3
"""
gmx_open_email.py — DEBUG/MANUAL TOOL (V15.6, Shadow-DOM-Fix)

Öffnet die GMX-Mailliste, penetriert das Shadow DOM (sc-webmailer-mail-list-h),
sucht die erste Email mit einem Keyword (Default: "fireworks") im Text, klickt
sie an und scannt den geöffneten Mailbody nach einer Verify-/Confirm-URL.

NICHT in den Rotator integriert — nur für Debug / manuellen Betrieb.

Voraussetzung: Chrome läuft bereits mit aktiver GMX-Session und CDP auf Port 9222
(z.B. via tools/manage_services.sh). Dieses Tool verbindet sich nur, es loggt
sich NICHT selbst ein.

Usage:
    python3 tools/gmx_open_email.py [--keyword fireworks] [--port 9222] [--timeout 30]
"""
import sys
import asyncio
import argparse
import logging
import re
import html as html_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gmx_open_email")

# JS: Shadow-DOM-durchdringende Scan-Funktion. Findet ALLE Elemente, deren Text
# das Keyword enthält — egal in welchem (verschachtelten) Shadow Root sie liegen.
SCAN_JS = r"""
(() => {
    const KW = (arguments[0] || '').toLowerCase();
    let out = [];
    function walk(root) {
        let nodes;
        try { nodes = root.querySelectorAll('*'); } catch (e) { return; }
        for (const el of nodes) {
            const txt = (el.innerText || el.textContent || '').trim();
            if (txt && txt.toLowerCase().includes(KW)) {
                const id = (el.getAttribute('id') || '').replace(/^id/, '') || null;
                out.push({
                    mailId: id,
                    tag: (el.tagName || '').toLowerCase(),
                    text: txt.slice(0, 400),
                    hasShadow: !!el.shadowRoot
                });
            }
            if (el.shadowRoot) walk(el.shadowRoot);
        }
    }
    if (document.body) walk(document.body);
    return out;
})()
"""

# JS: Klickt das erste (innerste/kürzeste) Element, das das Keyword enthält und
# klickbar wirkt. Penetriert ebenfalls das Shadow DOM.
CLICK_JS = r"""
(() => {
    const KW = (arguments[0] || '').toLowerCase();
    let best = null;
    let bestLen = Infinity;
    function walk(root) {
        let nodes;
        try { nodes = root.querySelectorAll('*'); } catch (e) { return; }
        for (const el of nodes) {
            const txt = (el.innerText || el.textContent || '').trim();
            if (txt && txt.toLowerCase().includes(KW)) {
                // bevorzuge das kürzeste Match — das ist meist der eigentliche
                // Listeneintrag/Link, nicht der umgebende Container
                if (txt.length < bestLen) { best = el; bestLen = txt.length; }
            }
            if (el.shadowRoot) walk(el.shadowRoot);
        }
    }
    if (document.body) walk(document.body);
    if (best) {
        const clickable = best.closest('a, button, [role="button"], [onclick], li, tr') || best;
        clickable.click();
        return true;
    }
    return false;
})()
"""

# JS: Shadow-DOM-durchdringende Volltext-Extraktion eines (Frame-)Dokuments.
TEXT_JS = r"""
(() => {
    let results = [];
    function traverse(node) {
        if (!node) return;
        if (node.shadowRoot) {
            const st = node.shadowRoot.body
                ? node.shadowRoot.body.innerText
                : (node.shadowRoot.documentElement ? node.shadowRoot.documentElement.innerText : '');
            if (st && st.trim()) results.push(st.trim());
            traverse(node.shadowRoot);
        }
        node.childNodes.forEach(child => {
            if (child.nodeType === Node.TEXT_NODE && child.textContent && child.textContent.trim()) {
                results.push(child.textContent.trim());
            } else if (child.nodeType === Node.ELEMENT_NODE) {
                const elText = (child.innerText || child.textContent || '').trim();
                if (elText) results.push(elText);
                traverse(child);
            }
        });
    }
    if (document.body) traverse(document.body);
    return results.join('\n');
})()
"""

URL_PATTERN = re.compile(
    r'https?://app\.fireworks\.ai/(?:signup/(?:confirm|verify)|confirm|verify|accounts/confirm)[^\s"\'<>]+'
)


async def main():
    ap = argparse.ArgumentParser(description="GMX Email öffnen + Shadow DOM scannen (Debug)")
    ap.add_argument("--keyword", default="fireworks", help="Keyword im Mail-Text (Default: fireworks)")
    ap.add_argument("--port", type=int, default=9222, help="CDP-Port von Chrome (Default: 9222)")
    ap.add_argument("--timeout", type=int, default=30, help="Wartezeit nach Mail-Klick in Sekunden")
    args = ap.parse_args()

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        logger.info(f"Verbinde mit Chrome via CDP auf Port {args.port} ...")
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{args.port}")

        # GMX-Page in einem der Kontexte finden
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                url = pg.url or ""
                if "navigator.gmx.net" in url or "gmx.net/mail" in url:
                    page = pg
                    break
            if page:
                break
        if page is None:
            page = await (browser.contexts[0].new_page() if browser.contexts else browser.new_page())

        logger.info("Lade Posteingang: https://navigator.gmx.net/mail")
        await page.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        body = await page.evaluate("() => document.body ? document.body.innerText : ''")
        if "Nicht eingeloggt" in body or ("anmelden" in body.lower()[:300] and "E-Mail" not in body):
            logger.error("GMX-Session ungültig — bitte zuerst einloggen (dieses Tool loggt nicht ein).")
            await browser.close()
            return

        # 1) Shadow-DOM-durchdringender Scan über ALLE Frames
        frames = list(page.frames)
        logger.info(f"Scanne {len(frames)} Frame(s) nach Keyword '{args.keyword}' (inkl. Shadow DOM) ...")
        target_frame = None
        matches = []
        for frame in frames:
            try:
                found = await frame.evaluate(SCAN_JS, args.keyword.lower())
            except Exception:
                found = []
            if found:
                target_frame = frame
                matches = found
                logger.info(f"  → {len(found)} Treffer im Frame {frame.url[:60]}")
                break

        if not target_frame:
            logger.warning(f"Keine Email mit '{args.keyword}' gefunden. Shadow DOM evtl. noch leer — länger warten?")
            await browser.close()
            return

        # Bereits eine URL im Listen-Text?
        joined = "\n".join(m.get("text", "") for m in matches)
        m = URL_PATTERN.search(joined)
        if m:
            url = html_module.unescape(m.group(0))
            logger.info(f"✅ Verify-URL bereits in der Mailliste gefunden:\n{url}")
            await browser.close()
            return

        # 2) Email anklicken (Shadow DOM)
        logger.info("Klicke erste passende Email an ...")
        try:
            clicked = await target_frame.evaluate(CLICK_JS, args.keyword.lower())
        except Exception as e:
            logger.warning(f"Klick fehlgeschlagen: {e}")
            clicked = False
        logger.info(f"Klick: {'✅' if clicked else '❌'}")
        await asyncio.sleep(args.timeout if args.timeout < 10 else 8)

        # 3) Mailbody scannen — neuer OOPIF-Frame kann erschienen sein
        logger.info("Scanne Mailbody (alle Frames, Shadow DOM) nach Verify-URL ...")
        for frame in page.frames:
            try:
                text = await frame.evaluate(TEXT_JS)
            except Exception:
                continue
            mm = URL_PATTERN.search(text or "")
            if mm:
                url = html_module.unescape(mm.group(0))
                logger.info(f"✅ Verify-URL gefunden in Frame {frame.url[:60]}:\n{url}")
                await browser.close()
                return

        logger.warning("Keine Verify-URL im Mailbody gefunden. Dump des größten Frames:")
        biggest = ""
        for frame in page.frames:
            try:
                t = await frame.evaluate(TEXT_JS)
            except Exception:
                t = ""
            if t and len(t) > len(biggest):
                biggest = t
        print((biggest or "(leer)")[:3000])
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
