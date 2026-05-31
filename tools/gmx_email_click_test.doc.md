# GMX Email Click — Shadow DOM Locator Solution

**Purpose:** Document the working method for clicking and reading emails in GMX via Playwright.

## Problem

GMX email UI uses multi-level Shadow DOM Custom Elements. The path to email items:

```
mail-list-container
  └── shadowRoot
        └── list-mail-list
              └── shadowRoot
                    └── list-mail-item × N  (the clickable email rows)
```

Standard approaches fail:
- `element.evaluate('el.click()')` — **does NOT work** on Shadow DOM custom elements
- `browser_snapshot_full_oopif()` — captures only **9 refs**, misses all 50 `list-mail-item` elements
- `document.querySelectorAll('list-mail-item')` on main page — finds **0 items** (they're in iframe + shadow DOM)

## Working Solution

### 1. Get mail iframe
```python
mail_frame = gmx_page.frame('mail')
```

### 2. Navigate to email list (via SPAWaker + click)
```python
from sin_browser_tools.core.spa_waker import SPAWaker
from sin_browser_tools.tools.interaction import browser_click_by_text
from sin_browser_tools.tools.accessibility import browser_snapshot_full_oopif

spa = SPAWaker()
await spa.wake_gmx_mail(gmx_page)       # Mounts GMX SPA
await browser_snapshot_full_oopif(pierce=True)  # Refresh refs after wake
await browser_click_by_text('E-Mail', role='button')  # Click nav button
await asyncio.sleep(8)
```

### 3. Get email items via Shadow DOM pierce
```python
items = await mail_frame.evaluate("""
(function() {
    var mlc = document.querySelector('mail-list-container');
    if (!mlc || !mlc.shadowRoot) return [];
    var mll = mlc.shadowRoot.querySelector('list-mail-list');
    if (!mll || !mll.shadowRoot) return [];
    var lis = mll.shadowRoot.querySelectorAll('list-mail-item');
    var result = [];
    lis.forEach(function(li) {
        var txt = (li.innerText || '').trim();
        if (txt.length > 5) result.push(txt.substring(0, 100));
    });
    return result;
})()
""")
# Returns: ['Vercel\n00:21\n🎉 You\'re in! $5 v0 credits...', ...]
```

### 4. Click via Playwright LOCATOR (NOT evaluate().click())
```python
# This WORKS:
await mail_frame.locator('list-mail-item').first.click(timeout=5000)

# This DOES NOT work:
await mail_frame.evaluate("(el) => el.click()", list_mail_item_element)
```

### 5. Read email body after click
```python
body = await mail_frame.evaluate("""
(function() {
    function walk(node, depth) {
        if (depth > 5) return '';
        var t = '';
        if (node.shadowRoot) {
            var children = node.shadowRoot.childNodes;
            for (var i = 0; i < children.length; i++) {
                var txt = children[i].innerText || '';
                if (txt.trim().length > 1) t += txt.trim() + '\\n';
                t += walk(children[i], depth + 1);
            }
        }
        var children2 = node.childNodes;
        for (var j = 0; j < children2.length; j++) {
            var txt2 = children2[j].innerText || '';
            if (txt2.trim().length > 1) t += txt2.trim() + '\\n';
            t += walk(children2[j], depth + 1);
        }
        return t;
    }
    return walk(document.body, 0);
})()
""")
```

## Root Cause of Snapshots Missing Email Items

`browser_snapshot_full_oopif(pierce=True)` only captures the main frame's AXTree with `pierce=True` (penetrates same-process iframes), but:
1. The `mail` iframe (`webmailer.gmx.net`) is cross-origin — `pierce` doesn't penetrate
2. Shadow DOM elements inside Custom Elements don't expose their children in the accessibility tree
3. `browser_snapshot` never walks the `mail` iframe's shadow DOM

## Key Files

- `tools/gmx_email_click_test.py` — working test script
- `agent_toolbox/core/gmx_service.py` — `read_otp_via_playwright()` uses similar approach

## GitHub Issues

- Issue #11: GMX email reading requires shadow DOM + iframe traversal
- Issue #6 (closed): browser_snapshot_full_oopif incomplete iframe capture

## Summary

| Method | Works? |
|--------|--------|
| `locator('list-mail-item').click()` | ✅ |
| `evaluate('el.click()')` | ❌ |
| `browser_snapshot` | ❌ (9 refs, 0 email items) |
| Shadow DOM JS pierce | ✅ (50 items found) |