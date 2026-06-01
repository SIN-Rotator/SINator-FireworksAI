# test_otp_mailbox.py — GMX OTP + Frame-Traversal Test

## Purpose
Test script for GMX OTP extraction via mailbox frame traversal and MailCheck extension. Used to verify `GmxService.read_otp_axtree_and_frames()` and `GmxService.read_fireworks_verification_email()` work end-to-end against the live GMX inbox.

## Dependencies
- **Imports:** `gmx_service.GmxService`, `playwright.async_api`
- **Requires:** Chrome CDP on port 9222 with active GMX session (Profile 73)
- **Environment:** `GMX_EMAIL`, `GMX_PASSWORD` (used by `GmxService._login`)

## Flow
1. Connect to existing Chrome via CDP
2. Login to GMX
3. Navigate to inbox
4. Run `read_otp_axtree_and_frames()` (frame-aware OTP scan)
5. Run `read_fireworks_verification_email()` (MailCheck extension)
6. Dump inbox page content for debugging

## Usage
```bash
python tools/test_otp_mailbox.py
```

## Known Caveats
- Requires Chrome Profile 73 to already have a GMX session
- May fail if GMX shows CAPTCHA or requires re-authentication
- Output is purely diagnostic — does not modify any state
