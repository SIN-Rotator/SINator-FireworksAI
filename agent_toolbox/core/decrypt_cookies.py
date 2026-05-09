#!/usr/bin/env python3
"""
Chrome Cookie Decryptor (macOS Keychain).

UNVERIFIED — This module has not been proven to work in the current setup.
The macOS Keychain may deny access to the Chrome Safe Storage Key, and
encrypted cookies copied from Profile 901 may not be decryptable if the
Keychain binding is path-dependent.

PURPOSE:
  Attempts to read Chrome's SQLite Cookies database, decrypt the
  encrypted_value column using the macOS Keychain-derived AES key, and export
  the cookies as plain JSON.

ARCHITECTURE:
  Chrome on macOS encrypts cookie values using AES-128-CBC with a key derived
  from the "Chrome Safe Storage" Keychain item via PBKDF2.

  Encryption scheme (reconstructed from public research; not official Google
  documentation):
    - Algorithm: AES-128-CBC
    - Key derivation: PBKDF2-HMAC-SHA1
      - Salt: b'saltysalt'
      - Iterations: 1003
      - Key length: 16 bytes
    - IV: 16 space characters (b' ' * 16)
    - Prefix stripping: encrypted_value may start with b'v10' or b'v11';
      these 3 bytes must be removed before decryption.
    - Padding: PKCS#7 (remove trailing bytes equal to the last byte value).

DEPENDENCIES:
  - pycryptodome (Crypto.Cipher.AES, Crypto.Protocol.KDF.PBKKDF2)
  - sqlite3 (standard library, but we use the CLI via subprocess because
    Python's sqlite3 may lack Full Disk Access on macOS)

WHAT COULD GO WRONG:
  1. Keychain access denied → get_safe_storage_key() raises CalledProcessError.
     Fix: Open Keychain Access, find "Chrome Safe Storage", allow Terminal.
  2. pycryptodome not installed → ImportError; install with:
     uv pip install --system pycryptodome
  3. SQLite database locked by running Chrome → We copy the DB via `cp` to a
     temp file first, but if Chrome is actively writing, the copy may be
     inconsistent (corrupted transactions).
  4. Wrong profile path → COOKIES_DB does not exist.
  5. Chrome changed encryption scheme (e.g. v12+) → decrypt_value() fails.
  6. macOS Full Disk Access prevents Python from reading the Cookies file
     → subprocess `cp` may also fail unless the terminal app has FDA.
  7. Cookie values are not UTF-8 after decryption → decode error; we use
     errors='replace' to avoid crashing.
"""

import sqlite3
import os
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# HARDCODED profile path. This MUST match the active Chrome profile.
CHROME_PROFILE = "/Users/jeremy/Library/Application Support/Google Chrome/Profile 901"

# Chrome's Cookies SQLite database path.
COOKIES_DB = os.path.join(CHROME_PROFILE, "Cookies")

# Output directory for decrypted cookie exports.
OUTPUT_DIR = Path("backup/session")


def get_safe_storage_key() -> bytes:
    """
    Fetch the Chrome Safe Storage Key from the macOS Keychain.

    WHAT IT DOES:
      Runs the `security find-generic-password` command to retrieve the
      password for the Keychain item named "Chrome Safe Storage" belonging
      to application "Chrome".

    WHY COMMAND LINE:
      The `security` CLI is the standard way to access Keychain items
      programmatically on macOS. It may trigger a GUI permission dialog
      on first use.

    Returns:
        The raw key as bytes (no trailing newline).

    Raises:
        subprocess.CalledProcessError: If the Keychain item is not found
        or access is denied.

    NOTE ON PERMISSIONS:
      On first run, macOS may show a dialog:
        "Terminal wants to access your Keychain data"
      Click "Always Allow" so the agent is never prompted again. If access
      is denied, open Keychain Access.app manually:
        1. Search "Chrome Safe Storage"
        2. Right-click → Get Info
        3. Access Control → Add Terminal.app → Allow.

    WHAT COULD GO WRONG:
      - Keychain locked → Prompts for user password; may hang in non-interactive
        environments.
      - Item deleted or renamed by Chrome update → CalledProcessError.
      - Wrong application name (should be exactly "Chrome") → Not found.
    """
    cmd = [
        "security",
        "find-generic-password",
        "-w",  # Output password only (no metadata).
        "-s",
        "Chrome Safe Storage",
        "-a",
        "Chrome",
    ]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return output.strip()
    except subprocess.CalledProcessError as e:
        print(f"Keychain Fehler: {e.output.decode('utf-8', errors='replace')}")
        print("   Tip: Open 'Keychain Access' -> search 'Chrome Safe Storage' ->")
        print("   Right-click -> 'Get Info' -> 'Access Control' -> allow Terminal")
        raise


def decrypt_value(encrypted_value: bytes, key: bytes) -> str:
    """
    UNVERIFIED — Decrypt a Chrome cookie value using AES-CBC.

    WHAT IT DOES:
      1. Derives a 16-byte AES key from `key` using PBKDF2-HMAC-SHA1
         with salt=b'saltysalt' and 1003 iterations.
      2. Strips the 'v10' or 'v11' prefix from encrypted_value if present.
      3. Decrypts using AES-128-CBC with IV=b' ' * 16.
      4. Removes PKCS#7 padding.
      5. Decodes the plaintext as UTF-8 (with replacement for invalid bytes).

    Args:
        encrypted_value: The raw encrypted bytes from Chrome's SQLite DB.
        key:             The Safe Storage Key from the Keychain.

    Returns:
        Decrypted string value.

    ASSUMPTIONS (UNVERIFIED):
      - Chrome uses AES-128-CBC (not AES-256-GCM or another algorithm).
      - The salt is exactly b'saltysalt'.
      - The iteration count is exactly 1003.
      - The IV is exactly 16 spaces.
      - The version prefix is 'v10' or 'v11' (3 bytes).

    WHAT COULD GO WRONG:
      - Chrome updated to a new encryption scheme → Decryption produces garbage
        or raises ValueError from pycryptodome.
      - encrypted_value is not bytes (e.g. already a string in the DB) →
        TypeError on startswith().
      - Key is wrong → Decryption succeeds but produces random bytes; UTF-8
        decode with errors='replace' masks the failure.
      - Last padding byte is >16 or 0 → PKCS#7 unpadding logic may strip too
        much or too little. This is a heuristic; malformed padding is possible.
    """
    try:
        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2
    except ImportError:
        print("pycryptodome not installed. Install: uv pip install --system pycryptodome")
        sys.exit(1)

    salt = b"saltysalt"
    iv = b" " * 16
    length = 16

    derived_key = PBKDF2(key, salt, dkLen=length, count=1003)
    cipher = AES.new(derived_key, AES.MODE_CBC, IV=iv)

    # Strip version prefix if present. Chrome prepends 'v10' or 'v11' to
    # distinguish encryption versions.
    if encrypted_value.startswith(b"v10") or encrypted_value.startswith(b"v11"):
        encrypted_value = encrypted_value[3:]

    decrypted = cipher.decrypt(encrypted_value)

    # PKCS#7 unpadding: the last byte tells us how many padding bytes to remove.
    # If the last byte is >16 or 0, we treat it as no padding (best effort).
    last_byte = decrypted[-1]
    if isinstance(last_byte, int) and last_byte <= 16:
        decrypted = decrypted[:-last_byte]

    return decrypted.decode("utf-8", errors="replace")


def export_cookies_to_json(db_path: str, output_path: str) -> str:
    """
    UNVERIFIED — Export decrypted cookies from Chrome's SQLite DB to JSON.

    WHAT IT DOES:
      1. Retrieve the Safe Storage Key from Keychain.
      2. Copy the Cookies SQLite DB to a temporary file (avoids locking).
      3. Open the copy with sqlite3 and read all rows from the cookies table.
      4. For each row:
         - If the plain `value` column is empty and `encrypted_value` exists,
           attempt decryption.
         - If decryption fails, store an error placeholder string.
         - Convert Chrome's expires_utc (Windows FILETIME epoch, microseconds
           since 1601-01-01) to Unix epoch seconds.
         - Map the samesite integer (0=None, 1=Lax, 2=Strict) to strings.
      5. Write the full list to output_path as JSON.
      6. Also write a filtered GMX-only list to gmx-cookies-decrypted.json.

    Args:
        db_path:      Path to Chrome's Cookies SQLite database.
        output_path:  Path for the full decrypted JSON output.

    Returns:
        Path to the saved JSON file (output_path).

    WHY COPY THE DB FIRST:
      Chrome holds a lock on the Cookies file while running. sqlite3 may fail
      with "database is locked" if we try to open it directly. Copying via
      the `cp` command bypasses the lock (at the cost of potentially reading
      an inconsistent state if Chrome is mid-transaction).

    ASSUMPTIONS (UNVERIFIED):
      - The cookies table schema matches the expected columns.
      - expires_utc uses the Windows FILETIME epoch (verified for Chrome on
        macOS as of 2024, but could change).
      - samesite values are 0, 1, 2 (Chrome's internal enum).

    WHAT COULD GO WRONG:
      - `cp` fails (permissions, disk full) → subprocess.CalledProcessError.
      - DB schema changed (new columns, renamed columns) → SQLite query fails.
      - All cookies are encrypted but key is wrong → All values become
        "[DECRYPT_ERROR: ...]".
      - Chrome is running and writes to the DB during the copy → The copy
        may be corrupted (SQLite WAL not flushed). This is rare but possible.
    """
    print(f"Reading Safe Storage Key from Keychain...")
    key = get_safe_storage_key()
    print(f"   Key obtained: {len(key)} bytes")

    print(f"Copying Cookie database (bypass SQLite lock)...")
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db.close()

    subprocess.run(["cp", db_path, temp_db.name], check=True)

    print(f"Opening copy: {temp_db.name}")
    conn = sqlite3.connect(temp_db.name)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT host_key, name, value, encrypted_value, path,
               expires_utc, is_secure, is_httponly, samesite
        FROM cookies
    """
    )

    decrypted_cookies = []
    encrypted_count = 0
    plain_count = 0
    error_count = 0

    for row in cursor.fetchall():
        (
            host,
            name,
            value,
            enc_value,
            path,
            expires,
            secure,
            httponly,
            samesite,
        ) = row

        if not value and enc_value:
            encrypted_count += 1
            try:
                if isinstance(enc_value, str):
                    enc_value = enc_value.encode("utf-8")
                value = decrypt_value(enc_value, key)
            except Exception as e:
                error_count += 1
                value = f"[DECRYPT_ERROR: {str(e)}]"
        else:
            plain_count += 1

        # Convert Chrome's expires_utc (Windows FILETIME in microseconds)
        # to Unix epoch seconds.
        # FILETIME epoch: 1601-01-01 00:00:00 UTC
        # Unix epoch:     1970-01-01 00:00:00 UTC
        # Difference:     11644473600 seconds
        # FILETIME is in 100-nanosecond ticks (1 tick = 0.1 microseconds).
        # Chrome stores expires_utc in microseconds since FILETIME epoch.
        # Formula: (expires_utc / 1_000_000) - 11_644_473_600
        if expires and expires != 0:
            unix_expires = (expires / 1000000) - 11644473600
        else:
            unix_expires = -1

        same_site_map = {0: "None", 1: "Lax", 2: "Strict"}

        decrypted_cookies.append(
            {
                "domain": host,
                "name": name,
                "value": value,
                "path": path or "/",
                "expires": unix_expires,
                "secure": bool(secure),
                "httpOnly": bool(httponly),
                "sameSite": same_site_map.get(samesite, "None"),
            }
        )

    conn.close()
    os.unlink(temp_db.name)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(decrypted_cookies, f, indent=2, ensure_ascii=False)

    # Write a filtered GMX-only file for convenience.
    gmx_cookies = [
        c for c in decrypted_cookies if "gmx" in c.get("domain", "")
    ]
    gmx_path = OUTPUT_DIR / "gmx-cookies-decrypted.json"
    with open(gmx_path, "w", encoding="utf-8") as f:
        json.dump(gmx_cookies, f, indent=2, ensure_ascii=False)

    print(f"\nDecryption complete:")
    print(f"   Total: {len(decrypted_cookies)} Cookies")
    print(f"   Encrypted decrypted: {encrypted_count}")
    print(f"   Already plaintext: {plain_count}")
    print(f"   Errors: {error_count}")
    print(f"   GMX Cookies: {len(gmx_cookies)}")
    print(f"\nSaved:")
    print(f"   {output_path}")
    print(f"   {gmx_path}")

    return str(output_path)


if __name__ == "__main__":
    """
    CLI entry point: decrypt cookies from Profile 901 and save to JSON.

    WHAT IT DOES:
      Calls export_cookies_to_json with the default COOKIES_DB path and writes
      to backup/session/decrypted-cookies.json.

    EXIT CODES:
      0 on success.
      1 on any exception (prints traceback).
    """
    try:
        output = OUTPUT_DIR / "decrypted-cookies.json"
        path = export_cookies_to_json(COOKIES_DB, str(output))
        print(f"\nReady for CDP Injection via Network.setCookie")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
