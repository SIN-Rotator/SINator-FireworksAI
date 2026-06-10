# GMX OTP Reader (`read_otp.py`)

Poll the GMX inbox for a verification/OTP email and extract its confirm URL.

## Dependencies

- **Imported by:** `gmx/__init__.py`
- **Imports:** `gmx._lib` (for `get_service`, `run`, `DEFAULT_CDP_PORT`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `read_otp(sender, retries, retry_delay, port)` | Poll inbox for verify URL; returns `otp_url` on success |

## Important Config/Limits

- Default: `retries=12`, `retry_delay=5` (60s total polling window)
- Delegates to `GmxService.read_otp()` (CDP-based MailCheck + OOPIF reader)
- `sender_filter` defaults to `"fireworks"`

## Known Caveats

- Fireworks verify emails may take up to 180s — increase retries if needed
- Uses CDP-based method (not Playwright-native) under the hood
