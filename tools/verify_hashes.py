#!/usr/bin/env python3
"""
═══ GMX PROTECTION — HASH VERIFICATION ═══

Prüft dass NICHTS an den kritischen Methoden in gmx_service.py
geändert wurde. Vergleicht SHA256-Hashes gegen data/gmx_hashes.json.

Usage:
    python tools/verify_hashes.py           # Quick check
    python tools/verify_hashes.py --verbose # Show all hashes

Exit codes:
    0 = ALL hashes match (code is untouched)
    1 = MISMATCH — code was modified, ROLLBACK REQUIRED
    2 = Hash file missing or corrupted
"""

import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SOURCE = ROOT / "agent_toolbox/core/gmx_service.py"
HASHES = ROOT / "protection/gmx_hashes.json"


def verify(verbose: bool = False) -> int:
    if not HASHES.exists():
        print(f"❌ Hash file not found: {HASHES}")
        return 2

    with open(HASHES) as f:
        data = json.load(f)

    methods = data.get("methods", {})
    with open(SOURCE) as f:
        source_lines = f.readlines()

    all_ok = True
    for name, info in methods.items():
        start, end = info["lines"].split("-")
        start, end = int(start), int(end)
        actual_code = "".join(source_lines[start - 1 : end])
        actual_hash = hashlib.sha256(actual_code.encode()).hexdigest()
        expected_hash = info["sha256"]

        if actual_hash == expected_hash:
            if verbose:
                print(f"  ✅ {name} ({info['line_count']} lines)")
        else:
            all_ok = False
            print(f"  ❌ {name} (lines {info['lines']}) — HASH MISMATCH")
            print(f"     Expected: {expected_hash[:16]}...")
            print(f"     Actual:   {actual_hash[:16]}...")
            print(f"     → ROLLBACK: git checkout v3-working -- agent_toolbox/core/gmx_service.py")

    if all_ok:
        v = data.get("version", "?")
        print(f"✅ ALL {len(methods)} hashes match — v3 code is INTACT (version={v})")
        return 0
    else:
        print(f"\n❌ INTEGRITY VIOLATION — code was modified!")
        print(f"   Rollback: git checkout v3-working -- agent_toolbox/core/gmx_service.py")
        return 1


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv
    sys.exit(verify(verbose))
