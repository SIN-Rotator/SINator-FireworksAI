# smspool_service.py

Docs: smspool_service.doc.md

## What
SMSPool integration for temporary UK phone numbers and OTP polling. ~$0.08 per UK number for Vercel (service 1553). Cancel unused numbers for full refund.

## Dependencies
- `httpx`

## API Endpoints
- `POST /purchase/sms` — order number (requires `country=NAME` not `country_id`!)
- `GET /sms/check` — poll SMS status
- `GET /sms/cancel` — cancel order (full refund if unused)

## Key Methods
- `order_uk_number(service)` — orders UK number for a given service
  - **CRITICAL**: Must use `country="United Kingdom"` (name), NOT `country_id`
  - Returns: `{success, number, order_id, raw}`
- `poll_otp(order_id, timeout, interval)` — polls until OTP arrives or timeout
  - Returns 6-digit OTP or None
- `cancel_order(order_id)` — cancels order, refunds $0.08 if unused

## Configuration
- `SMSPOOL_API_KEY` env var or constructor parameter
- `DEFAULT_COUNTRY_ID = "2"` (UK — ID from /country/retrieve_all)
  - **WARNING**: Was previously "16" which is KENYA, not UK!
- `DEFAULT_SERVICE = "1553"` (Vercel service ID from /service/retrieve_all)
  - **WARNING**: Was previously "vercel" (name) which returns HTTP 500!

## API Format Discovery (2026-06-03)
- `country_id=2` + `service="1553"` → HTTP 500 (wrong!)
- `country="United Kingdom"` + `service="1553"` → HTTP 200 ✅
- `service_id` parameter does NOT exist (returns 400)
- `service="vercel"` (name) → HTTP 500 (use ID "1553" instead)

## Response Format
Expected JSON fields from SMSPool:
- `order_id` / `id`
- `number` / `phonenumber` / `phone`
- `status` / `sms` / `message`
- `code` / `otp` / `sms_content`
- `cost` (e.g., "0.08" for Vercel UK)

## Known Issues
- SMSPool API requires country NAME for ordering, not ID (counterintuitive!)
- Service must be passed as numeric ID string ("1553"), not name ("vercel")
- Unused numbers can be cancelled for full refund within ~10 min expiry window
- Balance check: `/request/balance` returns `{"balance": "0.54"}`

## Cost Reference
| Service | Country | Cost |
|---|---|---|
| Vercel (1553) | UK | $0.08 |

## Usage Example
```python
from smspool_service import SMSPoolService
svc = SMSPoolService(api_key="nKw7Vo0JVNqPGkLSRYkn66KVockWfcoa")
order = await svc.order_uk_number(service="1553")
# Returns: +44 7898... number
otp = await svc.poll_otp(order["order_id"], timeout=120)
# Cancel if not used:
# await svc.cancel_order(order["order_id"])  # refunds $0.08
```