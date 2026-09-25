"""Verify forwarding with a synthetic sentinel. No network/API request."""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters,stdio_client
from manage import desired
from jev_client import ROOT

async def main():
    cfg=desired()
    sentinel="synthetic-env-"+uuid.uuid4().hex
    env={k:os.environ[k] for k in ("SYSTEMROOT","TEMP","TMP","PATH","USERPROFILE") if k in os.environ}
    env.update(cfg["env"])
    env["TYPESAFE_API_KEY"]=sentinel
    with (ROOT/"reports/mcp-environment-stderr.log").open("w",encoding="utf-8") as errlog:
        async with stdio_client(StdioServerParameters(command=cfg["command"],args=cfg["args"],cwd=cfg["cwd"],env=env),errlog=errlog) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=15) as session:
                await session.initialize()
                result=await session.call_tool("health",{})
                assert not result.is_error
                assert result.structured_content["credential_available"]
                assert result.structured_content["credential_source"]=="environment"
                assert sentinel not in result.model_dump_json()
    assert sentinel not in (ROOT/"reports/mcp-environment-stderr.log").read_text("utf-8")
    report={"status":"PASS","synthetic_only":True,"network_requests":0,"real_authentication_verified":False}
    (ROOT/"reports/mcp-environment-test.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))

if __name__=="__main__":asyncio.run(main())
