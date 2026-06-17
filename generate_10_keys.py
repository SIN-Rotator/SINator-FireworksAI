#!/usr/bin/env python3
"""
Generate 10 new Fireworks API keys via the rotation pipeline.

This script calls the rotate.py tool 10 times to create new keys
through the GMX alias rotation + Fireworks signup process.

Usage:
    python generate_10_keys.py

Note: This process takes approximately 30-40 minutes (3-4 minutes per key)
and will create new GMX aliases + Fireworks accounts.
"""
import asyncio
import json
import time
import sys
import subprocess
import os
from pathlib import Path
from typing import Dict, Any

# Configuration
TARGET_KEYS = 10
ROTATE_SCRIPT = Path(__file__).parent / "tools" / "rotate.py"
OUTPUT_FILE = Path(__file__).parent / "data" / "generated_keys.json"

# Environment variables (should be set in the system)
GMX_EMAIL = "delqhi@gmx.de"
GMX_PASSWORD = ""  # Set this via environment variable or edit the script

def log(message: str):
    """Log message with timestamp."""
    timestamp = time.strftime('%H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    with open(f"{OUTPUT_FILE}.log", "a") as f:
        f.write(log_line + "\n")

async def run_rotation(key_number: int) -> Dict[str, Any]:
    """Run the rotate.py script to generate one key."""
    log(f"--- Generating Key #{key_number}/{TARGET_KEYS} ---")
    
    # Prepare environment
    env = {
        **dict(os.environ),
        "GMX_PASSWORD": GMX_PASSWORD,
    }
    
    try:
        # Run rotate.py
        proc = await asyncio.create_subprocess_exec(
            "python3", str(ROTATE_SCRIPT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROTATE_SCRIPT.parent.parent),
            env=env,
        )
        
        # Read output
        stdout_bytes, _ = await proc.communicate()
        output = stdout_bytes.decode("utf-8", errors="replace").splitlines()
        
        # Extract key from output
        api_key = None
        alias_email = None
        for line in output:
            if "API Key:" in line:
                parts = line.split("API Key:")
                if len(parts) > 1:
                    api_key = parts[1].strip()
                    log(f"Found API key: {api_key[:12]}...")
            elif "Alias:" in line or "Alias created:" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    alias_email = parts[1].strip()
                    log(f"Found alias: {alias_email}")
        
        # Parse JSON output (rotate.py prints JSON)
        json_output = ""
        for line in output:
            if line.strip().startswith("{"):
                json_output += line
        
        if json_output:
            result = json.loads(json_output)
            if result.get("status") == "success":
                api_key = result.get("api_key")
                alias_email = result.get("alias_email")
                log(f"✅ Key #{key_number} generated: {alias_email} -> {api_key[:12]}...")
                return {
                    "status": "success",
                    "key_number": key_number,
                    "alias_email": alias_email,
                    "api_key": api_key,
                    "execution_time": result.get("execution_time", "unknown"),
                }
            else:
                log(f"❌ Key #{key_number} failed: {result.get('error', 'unknown error')}")
                return {
                    "status": "failed",
                    "key_number": key_number,
                    "error": result.get("error", "unknown"),
                    "output": result,
                }
        else:
            log(f"❌ Key #{key_number} - No JSON output found")
            return {
                "status": "failed",
                "key_number": key_number,
                "error": "No JSON output from rotate.py",
            }
            
    except Exception as e:
        log(f"❌ Key #{key_number} - Exception: {e}")
        return {
            "status": "failed",
            "key_number": key_number,
            "error": str(e),
        }
    
    return {
        "status": "failed",
        "key_number": key_number,
        "error": "Unknown failure",
    }

async def main():
    """Main function to generate 10 keys."""
    global GMX_PASSWORD
    GMX_PASSWORD = os.environ.get("GMX_PASSWORD", GMX_PASSWORD)
    
    # Prepare output
    log(f"Starting generation of {TARGET_KEYS} new Fireworks API keys")
    log(f"Target email: {GMX_EMAIL}")
    log(f"GMX password: {'***' if GMX_PASSWORD else 'NOT SET - PLEASE SET GMX_PASSWORD'}")
    log(f"Total estimated time: ~{TARGET_KEYS * 4} minutes (4 minutes per key)")
    log("")
    
    # Create output directory
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate keys
    results = []
    successes = 0
    failures = 0
    
    for i in range(1, TARGET_KEYS + 1):
        result = await run_rotation(i)
        results.append(result)
        
        if result["status"] == "success":
            successes += 1
        else:
            failures += 1
        
        # Wait between rotations (to avoid rate limits)
        if i < TARGET_KEYS:
            log(f"Waiting 60 seconds before next key...")
            await asyncio.sleep(60)
    
    # Save results
    summary = {
        "total_attempted": TARGET_KEYS,
        "successes": successes,
        "failures": failures,
        "generated_keys": [r for r in results if r["status"] == "success"],
        "failed_keys": [r for r in results if r["status"] == "failed"],
        "completion_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "estimated_total_time_minutes": TARGET_KEYS * 4,
    }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    log("\n" + "=" * 60)
    log("GENERATION SUMMARY")
    log("=" * 60)
    log(f"Total attempted: {summary['total_attempted']}")
    log(f"Successful: {summary['successes']}")
    log(f"Failed: {summary['failures']}")
    log(f"Success rate: {summary['successes']/summary['total_attempted']*100:.1f}%")
    log(f"Total time: ~{summary['estimated_total_time_minutes']} minutes")
    log(f"Results saved to: {OUTPUT_FILE}")
    
    if failures > 0:
        log(f"\n⚠️  {failures} keys failed. Check {OUTPUT_FILE} for details.")
        print("\nFailed keys:")
        for failed in summary['failed_keys']:
            print(f"  Key #{failed['key_number']}: {failed.get('error', 'unknown error')}")
    else:
        log("\n✅ All keys generated successfully!")
    
    # Show generated keys
    if successes > 0:
        log("\nGenerated Keys:")
        for key in summary['generated_keys']:
            print(f"  {key['key_number']}: {key['alias_email']} -> {key['api_key']}")
    
    return summary

if __name__ == "__main__":
    # Check if GMX_PASSWORD is set
    import os
    if not os.environ.get("GMX_PASSWORD") and not GMX_PASSWORD:
        print("\n❌ ERROR: GMX_PASSWORD is not set!")
        print("\nPlease set the GMX password either:")
        print("1. Export the environment variable:")
        print("   export GMX_PASSWORD='your_password_here'")
        print("2. Edit this script and set GMX_PASSWORD")
        print("\nThe script will exit now.")
        sys.exit(1)
    
    # Run the generation
    asyncio.run(main())
