"""Read-only protocol probe of a fresh installed Codex process. No model turn/login."""
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jev_client import ROOT

def probe():
    executable=shutil.which("codex")
    pending=queue.Queue()
    # Do not save stderr: another existing MCP may log its own private details.
    p=subprocess.Popen([executable,"app-server","--stdio"],cwd=str(ROOT),
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        text=True,encoding="utf-8",creationflags=subprocess.CREATE_NO_WINDOW)
    def reader():
        for line in p.stdout:
            try: pending.put(json.loads(line))
            except ValueError: pass
    threading.Thread(target=reader,daemon=True).start()
    counter=0
    def send(method,params,notification=False):
        nonlocal counter
        counter+=1
        msg={"method":method,"params":params}
        if not notification: msg["id"]=counter
        p.stdin.write(json.dumps(msg)+"\n");p.stdin.flush()
        if notification:return
        end=time.monotonic()+55
        while time.monotonic()<end:
            reply=pending.get(timeout=max(0.01,end-time.monotonic()))
            if reply.get("id")==counter:
                if "error" in reply: raise RuntimeError("RPC_ERROR_"+str(reply["error"].get("code")))
                return reply["result"]
        raise TimeoutError("CODEX_RPC_TIMEOUT")
    report={}
    try:
        initialized=send("initialize",{"clientInfo":{"name":"jev-integration-probe","version":"1.0.0"}})
        send("initialized",{},True)
        result=send("skills/list",{"cwds":[str(ROOT)],"forceReload":True})
        found=[{k:s.get(k) for k in ("name","path","scope","enabled")} for entry in result.get("data",[]) for s in entry.get("skills",[]) if s.get("name")=="typesafe-ai"]
        report["official_skill"]={"status":"PASS" if len(found)==1 else "FAIL","matches":found}
        result=send("mcpServerStatus/list",{"limit":100,"detail":"toolsAndAuthOnly"})
        found=[x for x in result.get("data",[]) if x.get("name")=="jev-bridge"]
        # Save only this integration's inventory, never other server configuration.
        from manage import desired
        valid=bool(found) and sorted(found[0].get("tools",{}))==sorted(desired()["enabled_tools"]) and not found[0].get("toolsError")
        report["fresh_codex_mcp_inventory"]={"status":"PASS" if valid else "BLOCKED","servers":found}
    except Exception as exc:
        report["probe_error"]={"status":"BLOCKED","reason":type(exc).__name__}
    finally:
        p.stdin.close()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
    (ROOT/"reports/codex-test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

if __name__=="__main__": print(json.dumps(probe(),ensure_ascii=False,indent=2))
