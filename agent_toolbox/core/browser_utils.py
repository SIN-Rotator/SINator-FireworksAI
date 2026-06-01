"""
SINator Browser Utilities V1.0 — React-kompatible Browser-Interaktion

Implementiert die CEO-Review Fixes:
  - JS-Injection statt DOM-Manipulation (React-kompatibel)
  - SPA-Transition Polling via MutationObserver
  - Main-Frame-Only OTP Scanning (keine Ad-iFrames)
  - Session Persistence via storage_state
"""
import logging
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Session storage path
SESSION_DIR = Path(__file__).parent.parent.parent / "data" / "sessions"
GMX_SESSION_FILE = SESSION_DIR / "gmx_session.json"
FIREWORKS_SESSION_FILE = SESSION_DIR / "fireworks_session.json"


async def accept_cookieyes_via_js(page) -> bool:
    try:
        result = await page.evaluate("""() => {
            if (window.CookieYes && typeof window.CookieYes.acceptAll === 'function') {
                window.CookieYes.acceptAll();
                return {method: 'api', success: true};
            }
            if (window.CookieYes && window.CookieYes.consent) {
                window.CookieYes.consent.acceptAll();
                return {method: 'consent_api', success: true};
            }
            try {
                const consent = {
                    necessary: true, functional: true, analytics: true,
                    performance: true, advertisement: true, timestamp: Date.now()
                };
                localStorage.setItem('cookieyes-consent', JSON.stringify(consent));
                localStorage.setItem('cky-consent', 'yes:' + btoa(JSON.stringify(consent)));
                return {method: 'localStorage', success: true};
            } catch (e) {
                return {method: 'none', success: false, error: e.message};
            }
        }""")
        if result.get('success'):
            logger.info(f"CookieYes accepted via {result.get('method')}")
            return True
        logger.warning(f"CookieYes JS injection failed: {result}")
        return False
    except Exception as e:
        logger.warning(f"CookieYes accept error: {e}")
        return False


async def wait_for_spa_transition(page, target_text: str, timeout: int = 30) -> bool:
    try:
        JS = """(args) => {
            var t = args.target_text, ms = args.timeout_ms, deadline = Date.now() + ms;
            if (document.body.innerText.includes(t)) return {found: true, method: 'immediate'};
            return new Promise(function(resolve) {
                var obs = new MutationObserver(function() {
                    if (document.body.innerText.includes(t)) { obs.disconnect(); resolve({found: true, method: 'observer'}); }
                    else if (Date.now() > deadline) { obs.disconnect(); resolve({found: false, method: 'timeout'}); }
                });
                obs.observe(document.body, {childList: true, subtree: true, characterData: true});
                setTimeout(function() {
                    obs.disconnect();
                    resolve({found: document.body.innerText.includes(t), method: 'timeout_check'});
                }, ms);
            });
        }"""
        result = await page.evaluate(JS, {"target_text": target_text, "timeout_ms": timeout * 1000})
        if result.get('found'):
            logger.info(f"SPA transition detected: '{target_text[:30]}...' via {result.get('method')}")
            return True
        logger.warning(f"SPA transition timeout waiting for: '{target_text[:30]}...'")
        return False
    except Exception as e:
        logger.warning(f"SPA transition error: {e}")
        return False


async def fill_react_input(page, selector: str, value: str) -> bool:
    try:
        JS = """(args) => {
            var sel = args.selector, val = args.value;
            var input = document.querySelector(sel);
            if (!input) return {success: false, error: 'Element not found'};
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, "value"
            ).set;
            nativeInputValueSetter.call(input, val);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            return {success: true, value: input.value};
        }"""
        result = await page.evaluate(JS, {"selector": selector, "value": value})
        if result.get('success'):
            logger.debug(f"React input filled: {selector}")
            return True
        logger.warning(f"React input fill failed: {result}")
        return False
    except Exception as e:
        logger.warning(f"React input error: {e}")
        return False


async def click_react_checkbox(page, label_text: str) -> bool:
    try:
        JS = """(args) => {
            var lt = args.label_text;
            var labels = document.querySelectorAll('label');
            for (var i = 0; i < labels.length; i++) {
                var label = labels[i];
                if (!label.textContent.includes(lt)) continue;
                if (label.querySelector('a')) {
                    var forAttr = label.getAttribute('for');
                    if (forAttr) {
                        var target = document.getElementById(forAttr);
                        if (target) { target.click(); return {success: true, method: 'for_attribute'}; }
                    }
                    var cb = label.querySelector('input[type="checkbox"], [role="checkbox"]');
                    if (cb) { cb.click(); return {success: true, method: 'nested_checkbox'}; }
                } else {
                    label.click();
                    return {success: true, method: 'label_click'};
                }
            }
            var cbs = document.querySelectorAll('[role="checkbox"]');
            for (var i = 0; i < cbs.length; i++) {
                var cb = cbs[i];
                var al = (cb.getAttribute('aria-label') || '').toLowerCase();
                if (al.includes(lt.toLowerCase())) { cb.click(); return {success: true, method: 'aria_label'}; }
            }
            return {success: false, error: 'Checkbox not found: ' + lt};
        }"""
        result = await page.evaluate(JS, {"label_text": label_text})
        if result.get('success'):
            logger.info(f"React checkbox clicked: '{label_text}' via {result.get('method')}")
            return True
        logger.warning(f"React checkbox not found: '{label_text}'")
        return False
    except Exception as e:
        logger.warning(f"React checkbox error: {e}")
        return False


async def save_session_state(context, filepath: Path) -> bool:
    """Save browser session state (cookies, localStorage) for fast restore."""
    try:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(filepath))
        logger.info(f"Session saved to {filepath}")
        return True
    except Exception as e:
        logger.warning(f"Session save error: {e}")
        return False


async def load_session_state(browser, filepath: Path):
    """Load browser session state (instant login in 0.1s)."""
    try:
        if filepath.exists():
            context = await browser.new_context(storage_state=str(filepath))
            logger.info(f"Session loaded from {filepath}")
            return context
        else:
            logger.info(f"No session file found: {filepath}")
            return None
    except Exception as e:
        logger.warning(f"Session load error: {e}")
        return None


async def extract_jwt_from_localstorage(page, key: str = "auth_token") -> Optional[str]:
    try:
        token = await page.evaluate("(k) => localStorage.getItem(k) || sessionStorage.getItem(k) || null", key)
        if token:
            logger.info(f"Token extracted from localStorage['{key}']: {token[:20]}...")
            return token
        logger.debug(f"No token found in localStorage['{key}']")
        return None
    except Exception as e:
        logger.warning(f"Token extraction error: {e}")
        return None


async def scan_main_frame_only(page, pattern: str) -> Optional[str]:
    """Scan ONLY main frame for pattern (keine Ad-iFrames!).
    
    Das verhindert das Scannen von 62 Ad-Tracker iFrames.
    """
    try:
        main_frame = page.main_frame
        text = await main_frame.evaluate("() => document.body.innerText")
        
        import re
        match = re.search(pattern, text)
        if match:
            logger.info(f"Pattern found in main frame: {match.group(0)[:50]}...")
            return match.group(0)
        else:
            logger.debug(f"Pattern not found in main frame")
            return None
    except Exception as e:
        logger.warning(f"Main frame scan error: {e}")
        return None


async def intercept_network_response(page, url_pattern: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
    """Intercept network response matching URL pattern.
    
    Statt DOM zu scrapen, intercepten wir den XHR-Call direkt.
    Wenn /api/v1/auth/signup 200 OK returned, wissen wir die Mail ist raus.
    """
    result = {"response": None}
    
    async def handle_response(response):
        if url_pattern in response.url:
            try:
                result["response"] = {
                    "url": response.url,
                    "status": response.status,
                    "body": await response.text() if response.status == 200 else None
                }
            except:
                result["response"] = {
                    "url": response.url,
                    "status": response.status,
                    "body": None
                }
    
    page.on("response", handle_response)
    
    try:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if result["response"]:
                logger.info(f"Network intercept: {result['response']['url'][:50]} -> {result['response']['status']}")
                return result["response"]
            await asyncio.sleep(0.5)
        
        logger.warning(f"Network intercept timeout for: {url_pattern}")
        return None
    finally:
        page.remove_listener("response", handle_response)
