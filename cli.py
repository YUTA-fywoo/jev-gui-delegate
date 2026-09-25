import argparse
import asyncio
import json
from pathlib import Path
from jev_client import ROOT, JevClient, BridgeError, health, capabilities

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["health", "capabilities", "smoke", "evaluate"])
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "health":
            result = health()
        elif args.command == "capabilities":
            result = capabilities()
        else:
            path = args.input if args.command == "evaluate" else ROOT / "example.json"
            if not path or path.stat().st_size > 65536:
                raise BridgeError("INVALID_INPUT_FILE")
            result = await JevClient().evaluate(json.loads(path.read_text("utf-8")))
    except BridgeError as exc:
        result = {"ok":False, "error":exc.code, "attempts":exc.attempts}
    except Exception:
        result = {"ok":False, "error":"INVALID_INPUT_FILE"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("ok") is False else 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
