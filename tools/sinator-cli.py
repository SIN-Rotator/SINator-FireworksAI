"""
SINator CLI — Generate Fireworks AI API Keys.

Requires Chrome + CUA-Driver + GMX session.
"""
import sys
import os
import json
import asyncio
import argparse
from pathlib import Path

_this_dir = Path(__file__).resolve().parent
_root = _this_dir.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "agent_toolbox" / "core"))

import agent_toolbox.core.gmx_service as _gmx
import agent_toolbox.core.fireworks_service as _fw
import agent_toolbox.core.pool_manager as _pool


async def generate_key(password: str, alias_name: str = None) -> dict:
    gmx = _gmx.GmxService()
    fw = _fw.FireworksService()
    pm = _pool.PoolManager()

    alias = alias_name or gmx.generate_alias_name()
    result = await fw.register(email=f"{alias}@gmx.de", password=password)
    if result.get("status") != "success":
        return {"status": "error", "error": result.get("error", "registration failed")}

    api_key = result.get("api_key")
    if api_key:
        pm.add_key(api_key, f"{alias}@gmx.de", alias.split("-")[0])
        pm.save()

    return {
        "status": "success",
        "api_key": api_key,
        "alias": f"{alias}@gmx.de",
        "execution_time": f"{result.get('execution_time', '?')}",
    }


def main():
    parser = argparse.ArgumentParser(description="SINator CLI — Generate Fireworks AI API Keys")
    parser.add_argument("--password", required=True, help="Password for Fireworks account")
    parser.add_argument("--alias", help="Custom GMX alias")
    parser.add_argument("--count", type=int, default=1, help="Number of keys")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    results = []
    for i in range(args.count):
        alias = args.alias
        if args.count > 1 and not alias:
            gmx = _gmx.GmxService()
            alias = gmx.generate_alias_name()
        elif args.count > 1:
            alias = f"{args.alias}-{i}"

        result = asyncio.run(generate_key(args.password, alias))
        results.append(result)

        if result["status"] == "success":
            print(f"[{i+1}/{args.count}] Key: {result['api_key']}", file=sys.stderr)
        else:
            print(f"[{i+1}/{args.count}] {result.get('error', 'failed')}", file=sys.stderr)
            break

    if args.json:
        print(json.dumps(results))
    else:
        for r in results:
            if r.get("api_key"):
                print(r["api_key"])


if __name__ == "__main__":
    main()
