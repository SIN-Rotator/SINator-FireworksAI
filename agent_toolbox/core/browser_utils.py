"""
SINator Browser Utilities V2.0 — React-kompatible Browser-Interaktion
(V18.0 Post-CEO-Fix Bugfixes)

Fixes from Issue #22:
  - F1: page.evaluate() mit dict-args statt f-string + positional
  - All evaluate() calls now use {"arg": val} pattern
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
    """Accept CookieYes via JS API injection (React-kompatibel).
    
    NICHT element.remove() verwenden - das zerstoert React State!
    """
    try:
        result = await page.evaluate("""() => {
            // Method 1: CookieYes API
            if (window.CookieYes && typeof window.CookieYes.acceptAll === 'function') {
                window.CookieYes.acceptAll();
                return {method: 'api', success: true};
            }
            
            // Method 2: CookieYes consent object
            if (window.CookieYes && window.CookieYes.consent) {
                window.CookieYes.consent.acceptAll();
                return {method: 'consent_api', success: true};
            }
            
            // Method 3: localStorage injection (fallback)
            try {
                const consent = {
                    necessary: true,
                    functional: true,
                    analytics: true,
                    performance: true,
                    advertisement: true,
                    timestamp: Date.now()
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
        else:
            logger.warning(f"CookieYes JS injection failed: {result}")
            return False
    except Exception as e:
        logger.warning(f"CookieYes accept error: {e}")
        return False


async def wait_for_spa_transition(page, target_text: str, timeout: int = 30) -> bool:
    """Wait for SPA DOM transition via MutationObserver.
    
    F1 FIX: Uses dict arg pattern instead of f-string + positional args.
    """
    try:
        # FIX F1: Pass args as dict, not f-string interpolation + positional
        result = await page.evaluate("""(args) => {
            const targetText = args.targetText;
            const timeoutMs = args.timeoutMs;
            return new Promise((resolve) => {
                // Check if already present
                if (document.body.innerText.includes(targetText)) {
                    resolve({found: true, method: 'immediate'});
                    return;
                }
                
                const deadline = Date.now() + timeoutMs;
                const observer = new MutationObserver((mutations, obs) => {
                    if (document.body.innerText.includes(targetText)) {
                        obs.disconnect();
                        resolve({found: true, method: 'observer'});
                    } else if (Date.now() > deadline) {
                        obs.disconnect();
                        resolve({found: false, method: 'timeout'});
                    }
                });
                
                observer.observe(document.body, {
                    childList: true,
                    subtree: true,
                    characterData: true
                });
                
                // Timeout fallback
                setTimeout(() => {
                    observer.disconnect();
                    if (document.body.innerText.includes(targetText)) {
                        resolve({found: true, method: 'timeout_check'});
                    } else {
                        resolve({found: false, method: 'timeout'});
                    }
                }, timeoutMs);
            });
        }""", {"targetText": target_text, "timeoutMs": timeout * 1000})
        
        if result.get('found'):
            logger.info(f"SPA transition detected: '{target_text[:30]}...' via {result.get('method')}")
            return True
        else:
            logger.warning(f"SPA transition timeout waiting for: '{target_text[:30]}...'")
            return False
    except Exception as e:
        logger.warning(f"SPA transition error: {e}")
        return False


async def wait_for_url_change(page, current_url_fragment: str, timeout: int = 15) -> bool:
    """Wait for URL to change away from current_url_fragment.
    
    O2 FIX: Better alternative to waiting for specific text like 'verify'.
    """
    try:
        start = asyncio.get_event_loop().time()
        deadline = start + timeout
        while asyncio.get_event_loop().time() < deadline:
            current_url = page.url
            if current_url_fragment not in current_url:
                logger.info(f"URL changed from '{current_url_fragment}' to '{current_url[:60]}'")
                return True
            await asyncio.sleep(0.5)
        logger.warning(f"URL change timeout: still contains '{current_url_fragment}'")
        return False
    except Exception as e:
        logger.warning(f"URL change wait error: {e}")
        return False


async def fill_react_input(page, selector: str, value: str) -> bool:
    """Fill React input with proper event dispatching.
    
    F1 FIX: Uses dict arg pattern.
    """
    try:
        # FIX F1: Pass args as dict
        result = await page.evaluate("""(args) => {
            const selector = args.selector;
            const value = args.value;
            const input = document.querySelector(selector);
            if (!input) return {success: false, error: 'Element not found'};
            
            // Get the native value setter
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, "value"
            ).set;
            
            // Set value via native setter
            nativeInputValueSetter.call(input, value);
            
            // Dispatch React-compatible events
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            
            return {success: true, value: input.value};
        }""", {"selector": selector, "value": value})
        
        if result.get('success'):
            logger.debug(f"React input filled: {selector}")
            return True
        else:
            logger.warning(f"React input fill failed: {result}")
            return False
    except Exception as e:
        logger.warning(f"React input error: {e}")
        return False


async def click_react_checkbox(page, label_text: str) -> bool:
    """Click React checkbox by label text.
    
    F1 FIX: Uses dict arg pattern.
    """
    try:
        # FIX F1: Pass args as dict
        result = await page.evaluate("""(args) => {
            const labelText = args.labelText;
            // Find label containing the text
            const labels = document.querySelectorAll('label');
            for (const label of labels) {
                if (label.textContent.includes(labelText)) {
                    // Check if label contains <a> tags (TOS trap!)
                    if (label.querySelector('a')) {
                        // Don't click label - find the target element instead
                        const forAttr = label.getAttribute('for');
                        if (forAttr) {
                            const target = document.getElementById(forAttr);
                            if (target) {
                                target.click();
                                return {success: true, method: 'for_attribute'};
                            }
                        }
                        // Try finding checkbox inside label
                        const cb = label.querySelector('input[type="checkbox"], [role="checkbox"]');
                        if (cb) {
                            cb.click();
                            return {success: true, method: 'nested_checkbox'};
                        }
                    } else {
                        // Safe to click label
                        label.click();
                        return {success: true, method: 'label_click'};
                    }
                }
            }
            
            // Fallback: find [role="checkbox"] with aria-label
            const checkboxes = document.querySelectorAll('[role="checkbox"]');
            for (const cb of checkboxes) {
                const ariaLabel = cb.getAttribute('aria-label') || '';
                if (ariaLabel.toLowerCase().includes(labelText.toLowerCase())) {
                    cb.click();
                    return {success: true, method: 'aria_label'};
                }
            }
            
            // Last resort: find div/span with checkbox-like behavior
            const all = document.querySelectorAll('div, span');
            for (const el of all) {
                if (el.textContent.trim() === labelText || 
                    el.textContent.includes(labelText)) {
                    const cb = el.querySelector('input[type="checkbox"], [role="checkbox"]');
                    if (cb) {
                        cb.click();
                        return {success: true, method: 'container_checkbox'};
                    }
                }
            }
            
            return {success: false, error: 'Checkbox not found'};
        }""", {"labelText": label_text})
        
        if result.get('success'):
            logger.info(f"React checkbox clicked: '{label_text}' via {result.get('method')}")
            return True
        else:
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
    """Extract JWT/Bearer token from localStorage for API bypass."""
    try:
        # FIX F1: Pass args as dict
        token = await page.evaluate("""(args) => {
            const key = args.key;
            return localStorage.getItem(key) || sessionStorage.getItem(key) || null;
        }""", {"key": key})
        
        if token:
            logger.info(f"Token extracted from localStorage['{key}']: {token[:20]}...")
            return token
        else:
            logger.debug(f"No token found in localStorage['{key}']")
            return None
    except Exception as e:
        logger.warning(f"Token extraction error: {e}")
        return None


async def scan_main_frame_only(page, pattern: str) -> Optional[str]:
    """Scan ONLY main frame for pattern (keine Ad-iFrames!)."""
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
    """Intercept network response matching URL pattern."""
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


def get_page_from_browser(browser) -> Any:
    """Helper to get a new page from browser (CDP-compatible).
    
    F5/O3 FIX: browser.new_page() throws on CDP connection.
    Use browser.contexts[0].new_page() instead.
    """
    if browser.contexts:
        return browser.contexts[0].new_page()
    else:
        return browser.new_page()
