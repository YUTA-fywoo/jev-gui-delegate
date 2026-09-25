import json
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jev_client import ROOT

def probe():
    p=subprocess.Popen([shutil.which("codex"),"app-server","--stdio"],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding="utf-8",creationflags=subprocess.CREATE_NO_WINDOW)
    q=queue.Queue();counter=0
    def reader():
        for line in p.stdout:
            try:q.put(json.loads(line))
            except ValueError:pass
    threading.Thread(target=reader,daemon=True).start()
    def rpc(method,params):
        nonlocal counter
        counter+=1;p.stdin.write(json.dumps({"id":counter,"method":method,"params":params})+"\n");p.stdin.flush()
        end=time.monotonic()+55
        while time.monotonic()<end:
            reply=q.get(timeout=max(0.01,end-time.monotonic()))
            if reply.get("id")==counter:return reply
    report={}
    try:
        rpc("initialize",{"clientInfo":{"name":"jev-delegation-discovery","version":"0.2.0"}})
        p.stdin.write('{"method":"initialized","params":{}}\n');p.stdin.flush()
        result=rpc("skills/list",{"cwds":[str(ROOT)],"forceReload":True})
        report["skill"]=[s for e in result.get("result",{}).get("data",[]) for s in e.get("skills",[]) if s.get("name")=="jev-gui-delegate"]
        result=rpc("mcpServerStatus/list",{"limit":100,"detail":"toolsAndAuthOnly"})
        report["mcp"]=[{"name":s.get("name"),"tools":list(s.get("tools",{})),"error":s.get("toolsError"),
          "run_task_schema_has_targets":'targets' in json.dumps(s.get('tools',{}).get('run_task',{}))} for s in result.get("result",{}).get("data",[]) if s.get("name")=="jev-bridge"]
        result=rpc("hooks/list",{"cwds":[str(ROOT)]})
        report["hooks"]=[h for e in result.get("result",{}).get("data",[]) for h in e.get("hooks",[]) if "gui_delegate" in str(h)]
        report["hook_rpc_keys"]=list(result.get("result",{}))
        if not report["hooks"]:report["hook_rpc"]=result
        report["status"]="PASS" if len(report["skill"])==1 and report["mcp"] and "run_task" in report["mcp"][0]["tools"] else "FAIL"
    finally:
        p.stdin.close()
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=3)
    (ROOT/"gui_delegate/reports/codex-discovery.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),"utf-8")
    return report
if __name__=="__main__":print(json.dumps(probe(),ensure_ascii=True,indent=2))
