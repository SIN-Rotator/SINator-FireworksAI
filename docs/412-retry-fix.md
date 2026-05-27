# 412 PRECONDITION_FAILED Retry Fix

## Problem

Hermes bricht bei 412-Fehlern sofort ab:

```
⚠️  Non-retryable error (HTTP 412) — trying fallback...
❌ Non-retryable error (HTTP 412). Aborting.
```

## Ursache

Hermes' `error_classifier.py` klassifiziert 412 als "Other 4xx → non-retryable format_error":

```python
# Zeile 789 in agent/error_classifier.py
if 400 <= status_code < 500:
    return result_fn(FailoverReason.format_error, retryable=False, ...)
```

Aber 412 PRECONDITION_FAILED bei sinator.delqhi.com bedeutet oft:
- Ein interner API-Key ist "suspended" (Billing-Limit)
- Andere Keys im Pool funktionieren noch

## Lösung

412 mit "suspended" im Body → `billing` + `retryable=True` + `should_rotate_credential=True`:

```python
# Vor dem generischen "Other 4xx"-Catch:
if status_code == 412:
    if "suspended" in error_msg:
        return result_fn(
            FailoverReason.billing,
            retryable=True,
            should_rotate_credential=True,
            should_fallback=True,
        )
    return result_fn(FailoverReason.format_error, retryable=False, should_fallback=True)
```

## Anwendung

```bash
# Patch anwenden
cd ~/.hermes/hermes-agent/
git apply /path/to/error_classifier_412.patch

# Oder manuell editieren:
# ~/.hermes/hermes-agent/agent/error_classifier.py, Zeile 789
```

## Warum es funktioniert

| Vorher | Nachher |
|--------|---------|
| 412 → `format_error` → `retryable=False` → **Abbruch** | 412 + "suspended" → `billing` → `retryable=True` → **Retry** |
| Erster Key im Pool suspended → Tot | Retry trifft anderen Key im Pool → Funktioniert |

## Referenz

- Datei: `~/.hermes/hermes-agent/agent/error_classifier.py`
- Zeile: 789 (vor dem generischen 400-499 Catch)
- Getestet: 2026-05-26, Survey #2 erfolgreich completed
