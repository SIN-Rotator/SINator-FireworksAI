# GMX Alias Deletion (`delete_alias.py`)

Delete the existing GMX alias, if any.

## Dependencies

- **Imported by:** `gmx/__init__.py`, `gmx/rotate_alias.py`
- **Imports:** `gmx._lib` (for `connect_gmx_page`, `get_credentials`, `run`, `DEFAULT_CDP_PORT`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `delete_alias(email, password, port)` | Delete current alias; returns `no_alias` if none exists |

## Important Config/Limits

- Uses `connect_gmx_page()` for page connection rather than bare `get_service()`
- Verifies deletion via `_verify_alias()` after a 2-second wait
- Internally calls `GmxService._delete_alias()` — **V19.3 delete selector fix**

## Known Caveats

- Returns `no_alias` status, not an error, when no alias exists
- Credentials passed through call chain for `_navigate_to_all_email_addresses()`

---

## ⚠️ V19.3 — Delete-Icon in `js-template is-hidden` (DO NOT TOUCH v19.3-gmx-delete-fixed)

**GMX rendert das Delete-Icon in einem HIDDEN TEMPLATE außerhalb der Row:**

```html
<div class="js-template is-hidden" data-template-name="hoverMenu">
  <a class="table-hover_icon icon-link" title="E-Mail-Adresse löschen">...</a>
</div>
```

Bei Hover über die Row wird das Template **unhidden** (`is-hidden` Klasse weg).

### Selektor-Logik (V19.3)
```javascript
// Suche 1 (bevorzugt): eindeutiger Selektor
'a.table-hover_icon[title*="löschen"], a.table-hover_icon[title*="Löschen"]'
// → nur sichtbare Elemente (r.width > 5 && r.height > 5)

// Suche 2 (fallback): alle <a> mit "lösch" im title
'a[title*="lösch" i]'
```

**NICHT** `rows[i].querySelector('[title*="lösch"]')` — sucht INNERHALB der Row und findet NICHTS.

### Delete-Flow (5 Schritte)
1. Finde Row (`.table_body-row` mit Alias) → Center `(cx, cy)`
2. CDP `Input.dispatchMouseEvent type='mouseMoved'` an `(cx, cy)`
3. Sleep 1.5s (Template-Unhide braucht Zeit)
4. Suche Delete-Icon global mit obigem Selektor
5. CDP `mousePressed` + `mouseReleased` an Icon-Position
6. Sleep 3s (Confirm-Dialog)
7. Klicke OK-Button (`text === 'OK'`, sichtbar)
8. Sleep 2s + Verifikation: Alias nicht mehr in `document.body.innerText`

### Verifikation
```bash
python3 debug/test_delete_fix.py
# Erwartet: "DELETION SUCCESS" für einen Test-Alias
```
