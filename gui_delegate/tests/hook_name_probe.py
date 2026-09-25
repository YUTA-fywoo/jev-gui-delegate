"""Temporary read-only tool-name probe: does not block or record arguments."""
import json,os,sys,time
from pathlib import Path
try:
    raw=b""
    while len(raw)<1024*1024:
        chunk=os.read(sys.stdin.fileno(),65536)
        if not chunk:break
        raw+=chunk
        try:value=json.loads(raw);break
        except ValueError:continue
    value=json.loads(raw)
    with (Path(__file__).resolve().parents[1]/"private/hook-names.jsonl").open("a",encoding="utf-8") as out:
        out.write(json.dumps({"time":time.time(),"event":value.get("hook_event_name"),"tool_name":value.get("tool_name"),"keys":list(value)})+"\n")
except Exception:pass
print("{}")
