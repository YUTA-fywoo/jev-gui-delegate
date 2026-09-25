"""Direct + subprocess MCP acceptance, using only bundled synthetic data."""
import argparse
import asyncio
import json
import subprocess
import sys
from jev_client import ROOT,JevClient,BridgeError
sys.path.insert(0,str(ROOT/"tests"))
from mcp_probe import probe

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--all",action="store_true",help="Also run failure, Codex inventory and synthetic GUI tests.")
    args=parser.parse_args()
    if args.all:
        for script in ("test_failures.py","test_registration.py","test_credentials.py","test_mcp_environment.py","gui_probe.py","codex_probe.py"):
            subprocess.run([sys.executable,str(ROOT/"tests"/script)],check=True)
    try:
        result=await JevClient().evaluate(json.loads((ROOT/"example.json").read_text("utf-8")))
        direct={"status":"PASS","result":result}
    except BridgeError as exc:
        blocked={"MISSING_API_KEY","CREDENTIAL_STORE_UNAVAILABLE","AUTHENTICATION_FAILED","PERMISSION_DENIED","BILLING_BLOCKED","NETWORK_ERROR","NETWORK_TIMEOUT","RATE_LIMITED","SERVICE_OVERLOADED"}
        direct={"status":"BLOCKED" if exc.code in blocked else "FAIL","error":exc.code,"attempts":exc.attempts}
    (ROOT/"reports/direct-test.json").write_text(json.dumps(direct,indent=2,ensure_ascii=False),encoding="utf-8")
    mcp=await probe()
    from write_manifest import write_manifest
    manifest=write_manifest()
    output={"direct_api":direct,"mcp_live_evaluate":mcp["live_evaluate"],"manifest":str(manifest)}
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return 0 if direct["status"]==mcp["live_evaluate"]["status"]=="PASS" else 2

if __name__=="__main__":raise SystemExit(asyncio.run(main()))
