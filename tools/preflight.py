#!/usr/bin/env python3
"""
═══ PREFLIGHT CHECK — MUST PASS BEFORE ANY CODE CHANGE ═══

Usage:
    python tools/preflight.py              # Full check
    python tools/preflight.py --hashes     # Hash-only check
    python tools/preflight.py --rotate     # Rotate-only check

Exit codes:
    0 = ALL CHECKS PASSED — safe to edit
    1 = INTEGRITY VIOLATION — DO NOT EDIT, ROLLBACK FIRST
    2 = Runtime error (Chrome not running, etc.)
"""

import subprocess, sys, json
from pathlib import Path

ROOT = Path(__file__).parent.parent
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"
BOLD = "\033[1m"

def ok(msg): print(f"  {GREEN}✅{RESET} {msg}")
def fail(msg): print(f"  {RED}❌{RESET} {msg}")

def check_hashes():
    """Verify SHA256 hashes of 18 critical gmx_service methods."""
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

def check_rotate():
    """Run a full alias rotation to verify end-to-end flow."""
    print(f"\n{BOLD}[2/3] GMX ALIAS ROTATION{RESET}")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/gmx_alias_tool.py"), "rotate"],
        capture_output=True, text=True, timeout=180
    )
    if result.returncode == 0 and "success" in result.stdout.lower():
        # Extract the alias name
        for line in result.stdout.split('\n'):
            if 'Created:' in line:
                ok(f"Rotation SUCCESS — {line.strip()}")
                return True
        ok("Rotation SUCCESS")
        return True
    else:
        fail("Rotation FAILED")
        print(f"         {result.stdout.strip()[-500:]}")
        print(f"         {result.stderr.strip()[-200:]}")
        return False

def check_git_clean():
    """Verify no uncommitted changes to protected files."""
    print(f"\n{BOLD}[3/3] GIT STATUS{RESET}")
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
    print(f"Protection: 18 SHA256 hashes + git tag v3-working")
    print(f"Critical files: gmx_service.py, fireworks_service.py, gmx_alias_tool.py")
    
    args = set(sys.argv[1:])
    all_checks = not args  # default: all checks
    
    passed = True
    
    if all_checks or "--hashes" in args:
        passed &= check_hashes()
    
    if all_checks or "--rotate" in args:
        passed &= check_rotate()
    
    if all_checks:
        passed &= check_git_clean()
    
    print()
    if passed:
        print(f"{GREEN}{BOLD}✅ ALL CHECKS PASSED — safe to edit{RESET}")
        print(f"   Remember: NEVER modify hash-protected methods without")
        print(f"   running preflight AFTER the edit to verify integrity.")
        return 0
    else:
        print(f"{RED}{BOLD}❌ PREFLIGHT FAILED — DO NOT EDIT{RESET}")
        print(f"   Rollback: git checkout v3-working -- agent_toolbox/core/gmx_service.py")
        print(f"   Then: python tools/preflight.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())
