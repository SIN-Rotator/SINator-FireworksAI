#!/usr/bin/env python3
"""
Auto-Key-Swap für OpenCode CLI.

Bei Fireworks Rate-Limit (402/429) diesen Key aus dem Pool als verbraucht
melden und einen neuen Key in ~/.local/share/opencode/auth.json eintragen.
KEIN Session-Neustart nötig — OpenCode liest auth.json bei jedem API-Call.

Usage:
    python tools/swap_key.py              # Auto-detect bad key from auth.json
    python tools/swap_key.py fw_xxx       # Specific key to report

Docs: swap_key.doc.md
"""
import json
import sys
import urllib.request
from pathlib import Path

AUTH_FILE = Path.home() / ".local/share/opencode/auth.json"
SINATOR_API = "http://localhost:8000/api/v1"
MODEL = "accounts/fireworks/models/deepseek-v4-pro"

def api(path, data=None):
    url = f"{SINATOR_API}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def swap_key(bad_key: str):
    # 1. Report bad key
    result = api("/pool/report", {"api_key": bad_key})
    if not result.get("swapped"):
        print(f"❌ No available keys in pool. Run rotation!")
        return False
    
    new_key = result["new_key"]
    print(f"✅ Key swapped: {bad_key[:20]}... → {new_key[:20]}...")
    print(f"   New alias: {result['new_alias']}")
    
    # 2. Update OpenCode auth.json
    auth = {}
    if AUTH_FILE.exists():
        auth = json.loads(AUTH_FILE.read_text())
    
    auth["fireworks"] = new_key
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(auth, indent=2))
    print(f"   Updated: {AUTH_FILE}")
    
    return True

def get_current_key():
    """Read current Fireworks key from auth.json"""
    if AUTH_FILE.exists():
        auth = json.loads(AUTH_FILE.read_text())
        return auth.get("fireworks")
    return None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Swap Fireworks API key in OpenCode")
    parser.add_argument("key", nargs="?", help="API key to report as bad")
    args = parser.parse_args()
    
    bad_key = args.key or get_current_key()
    if not bad_key:
        print("❌ No Fireworks key found. Use: python tools/swap_key.py fw_xxx")
        sys.exit(1)
    
    success = swap_key(bad_key)
    sys.exit(0 if success else 1)
