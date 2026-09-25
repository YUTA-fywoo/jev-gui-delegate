"""Credential enrollment over an anonymous pipe; never accepts a key in argv."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credentials import save_key, resolve_key

def main():
    stage = "stdin"
    try:
        value = sys.stdin.read(4097).strip()
        if len(value) > 4096:
            return 1
        stage = "save"
        save_key(value)
        stage = "verify"
        saved, source = resolve_key()
        if saved != value or source != "windows-credential-manager":
            return 2
        return 0
    except Exception as exc:
        print(json.dumps({"saved": False, "stage":stage, "error_type": type(exc).__name__, "windows_error": getattr(exc, "winerror", None)}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
