#!/usr/bin/env python3
"""
═══ PREFLIGHT CHECK — MUST PASS BEFORE ANY CODE CHANGE ═══

Usage:
    python tools/preflight.py

Exit codes:
    0 = ALL CHECKS PASSED — safe to edit
    1 = INTEGRITY VIOLATION — DO NOT EDIT
"""

import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"
BOLD = "\033[1m"

def ok(msg): print(f"  {GREEN}✅{RESET} {msg}")
def fail(msg): print(f"  {RED}❌{RESET} {msg}")

def check_hashes():
    """Verify SHA256 hashes of critical gmx_service methods."""
    print(f"\n{BOLD}[1/3] HASH VERIFICATION{RESET}")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/verify_hashes.py")],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        ok("All 18 method hashes match — code is INTACT")
        return True
    else:
        fail("HASH MISMATCH — code was modified!")
        print(f"         {result.stdout.strip()}")
        return False

def check_git_clean():
    """Verify no uncommitted changes to protected files."""
    print(f"\n{BOLD}[2/2] GIT STATUS{RESET}")
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--",
         "agent_toolbox/core/gmx_service.py",
         "agent_toolbox/core/fireworks_service.py",
         "tools/gmx_alias_tool.py"],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.stdout.strip():
        fail("UNCOMMITTED changes to protected files:")
        for line in result.stdout.strip().split('\n'):
            print(f"         {line}")
        print(f"         → git checkout v3-working -- <file> to restore")
        return False
    ok("No uncommitted changes to protected files")
    return True

def main():
    print(f"{BOLD}═══ PREFLIGHT CHECK — SINator v3 ═══{RESET}")
    print(f"GMX Alias Tool: python tools/gmx_alias_tool.py rotate")
    print(f"Protection: 18 SHA256 hashes + git tag v3-working")

    passed = True
    passed &= check_hashes()
    passed &= check_git_clean()

    print()
    if passed:
        print(f"{GREEN}{BOLD}✅ ALL CHECKS PASSED — safe to edit{RESET}")
        return 0
    else:
        print(f"{RED}{BOLD}❌ PREFLIGHT FAILED — DO NOT EDIT{RESET}")
        print(f"   Rollback: git checkout v3-working -- agent_toolbox/core/gmx_service.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())