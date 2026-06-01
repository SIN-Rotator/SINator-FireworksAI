import logging
import asyncio
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


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
            return True
        return False
    except Exception as e:
        logger.warning(f"CookieYes accept error: {e}")
        return False


async def wait_for_spa_transition(page, target_text: str, timeout: int = 30) -> bool:
    try:
        result = await page.evaluate("""(args) => {
            const targetText = args.targetText;
            const timeoutMs = args.timeoutMs;
            return new Promise((resolve) => {
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
                    childList: true, subtree: true, characterData: true
                });
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
            return True
        return False
    except Exception as e:
        logger.warning(f"SPA transition error: {e}")
        return False


async def fill_react_input(page, selector: str, value: str) -> bool:
    try:
        result = await page.evaluate("""(args) => {
            const selector = args.selector;
            const value = args.value;
            const input = document.querySelector(selector);
            if (!input) return {success: false, error: 'Element not found'};
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, "value"
            ).set;
            nativeInputValueSetter.call(input, value);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            return {success: true, value: input.value};
        }""", {"selector": selector, "value": value})
        if result.get('success'):
            return True
        logger.warning(f"React input fill failed: {result}")
        return False
    except Exception as e:
        logger.warning(f"React input error: {e}")
        return False


async def click_react_checkbox(page, label_text: str) -> bool:
    try:
        result = await page.evaluate("""(args) => {
            const labelText = args.labelText;
            const labels = document.querySelectorAll('label');
            for (const label of labels) {
                if (label.textContent.includes(labelText)) {
                    if (label.querySelector('a')) {
                        const forAttr = label.getAttribute('for');
                        if (forAttr) {
                            const target = document.getElementById(forAttr);
                            if (target) { target.click(); return {success: true, method: 'for_attribute'}; }
                        }
                        const cb = label.querySelector('input[type="checkbox"], [role="checkbox"]');
                        if (cb) { cb.click(); return {success: true, method: 'nested_checkbox'}; }
                    } else {
                        label.click();
                        return {success: true, method: 'label_click'};
                    }
                }
            }
            const checkboxes = document.querySelectorAll('[role="checkbox"]');
            for (const cb of checkboxes) {
                const ariaLabel = cb.getAttribute('aria-label') || '';
                if (ariaLabel.toLowerCase().includes(labelText.toLowerCase())) {
                    cb.click(); return {success: true, method: 'aria_label'};
                }
            }
            return {success: false, error: 'Checkbox not found'};
        }""", {"labelText": label_text})
        if result.get('success'):
            return True
        logger.warning(f"React checkbox not found: '{label_text}'")
        return False
    except Exception as e:
        logger.warning(f"React checkbox error: {e}")
        return False


async def wait_for_url_change(page, target_substring: str, timeout: int = 30) -> bool:
    start_url = page.url
    for _ in range(timeout):
        await asyncio.sleep(1)
        current = page.url
        if target_substring in current and current != start_url:
            return True
    return False


async def scan_main_frame_only(page, pattern: str) -> Optional[str]:
    try:
        text = await page.main_frame.evaluate("() => document.body.innerText")
        match = re.search(pattern, text)
        if match:
            return match.group(0)
        return None
    except Exception as e:
        logger.warning(f"Main frame scan error: {e}")
        return None
