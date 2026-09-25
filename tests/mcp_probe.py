import asyncio
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from jev_client import ROOT
from manage import desired
from manage import codex_home
import tomllib

async def probe(live=True):
    entry=tomllib.loads((codex_home()/"config.toml").read_text("utf-8"))["mcp_servers"]["jev-bridge"]
    assert entry==desired(), "Registered command differs from this installation"
    # No copied parent secrets: reproduces an MCP child with a minimal environment.
    env={k:os.environ[k] for k in ("SYSTEMROOT","WINDIR","TEMP","TMP","USERPROFILE","PATH") if k in os.environ}
    env.update(entry["env"])
    # Mirrors configured env_vars. Credential Manager fallback works even for an old GUI parent.
    if os.environ.get("TYPESAFE_API_KEY"):
        env["TYPESAFE_API_KEY"]=os.environ["TYPESAFE_API_KEY"]
    params=StdioServerParameters(command=entry["command"],args=entry["args"],cwd=entry["cwd"],env=env)
    report={}
    with (ROOT/"reports/mcp-stderr.log").open("w",encoding="utf-8") as errlog:
        async with stdio_client(params,errlog=errlog) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=55) as session:
                initialized=await session.initialize()
                listed=await session.list_tools()
                names=sorted(t.name for t in listed.tools)
                assert names == sorted(desired()["enabled_tools"])
                report["tools_list"]={"status":"PASS","names":names,"server":initialized.server_info.model_dump()}
                for name in ("health","capabilities"):
                    result=await session.call_tool(name,{})
                    assert not result.is_error
                    report[name]={"status":"PASS","result":result.structured_content}
                invalid=await session.call_tool("evaluate",{"state":{},"questions":{}})
                assert invalid.is_error and invalid.structured_content["error"]=="INVALID_INPUT"
                report["invalid_input"]={"status":"PASS"}
                if live:
                    if not report["health"]["result"]["credential_available"]:
                        missing=await session.call_tool("evaluate",json.loads((ROOT/"example.json").read_text("utf-8")))
                        assert missing.is_error and missing.structured_content["error"] == "MISSING_API_KEY"
                        report["live_evaluate"]={"status":"BLOCKED","reason":"MISSING_API_KEY"}
                    else:
                        result=await session.call_tool("evaluate",json.loads((ROOT/"example.json").read_text("utf-8")))
                        blocked={"MISSING_API_KEY","CREDENTIAL_STORE_UNAVAILABLE","AUTHENTICATION_FAILED","PERMISSION_DENIED","BILLING_BLOCKED","NETWORK_ERROR","NETWORK_TIMEOUT","RATE_LIMITED","SERVICE_OVERLOADED"}
                        status="PASS" if not result.is_error else ("BLOCKED" if result.structured_content.get("error") in blocked else "FAIL")
                        report["live_evaluate"]={"status":status,"result":result.structured_content}
    (ROOT/"reports/mcp-test.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    return report

if __name__ == "__main__":
    print(json.dumps(asyncio.run(probe()),indent=2,ensure_ascii=False))
