# GMX Alias Rotation (`rotate_alias.py`)

Atomically delete the old GMX alias and create a new one in a single pass.

## Dependencies

- **Imported by:** `gmx/__init__.py`
- **Imports:** `gmx._lib` (for `get_credentials`, `get_service`, `run`, `DEFAULT_CDP_PORT`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `rotate_alias(name, email, password, port)` | Delete current alias + create new one; returns both old and new addresses |

## Important Config/Limits

- Delegates to `GmxService.rotate_alias()` (production rotator logic)
- Random name generated if `name` is `None`
- Credentials fall back to project config
- **V19.3 Fix angewendet** auf internen `_delete_alias()` Aufruf — Delete-Icon-Selektor repariert

## Known Caveats

- Requires active GMX session
- GMX FreeMail allows only one alias, so rotation is delete-then-create (not parallel)

---

## V19.3 Delete Fix (IMMORTAL TAG: `v19.3-gmx-delete-fixed`)

`rotate_alias()` ruft intern `GmxService._delete_alias()` auf, welcher am 2026-06-02 repariert wurde:

**Bug:** Delete-Link sitzt in `<div class="js-template is-hidden">` Block AUSSERHALB der Row. Bei Hover wird das Template unhidden.

**Fix:** Spezifischer Selektor `a.table-hover_icon[title*="löschen"]` mit Visibility-Check (`r.width > 5 && r.height > 5`).

**Verifikation:** `debug/test_delete_fix.py` — `_delete_alias("test-1779947387@alphafrau.de")` → SUCCESS in 158.5s Rotation.

**DO NOT TOUCH** ohne Diagnose. Siehe `gmx/delete_alias.doc.md` für Details.
