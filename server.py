"""Small MCP stdio surface. stdout belongs exclusively to MCP."""
import asyncio
import json
import logging
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from jev_client import JevClient, EvaluationInput, BridgeError, health, capabilities
from gui_delegate import service as gui
from gui_delegate.schema import Resume,Cancel,Diagnose
from gui_delegate.security import Stop
from gui_delegate.contract_io import input_schema as contract_input_schema
from pydantic import ValidationError

logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
EMPTY = {"type":"object", "properties":{}, "additionalProperties":False}

async def list_tools(ctx, params):
    result=types.ListToolsResult(tools=[
        types.Tool(name="health", description="Check local Jev bridge readiness without an API request.", inputSchema=EMPTY),
        types.Tool(name="capabilities", description="Describe typed decisions, limits and GUI boundaries.", inputSchema=EMPTY),
        types.Tool(name="evaluate", description="Send provided text/JSON state and typed Choice/Noul/Score questions to TypeSafe cloud. Consumes API usage. Returns judgments only; executes no GUI action.", inputSchema=EvaluationInput.model_json_schema()),
        types.Tool(name="run_task",description="Run a bounded native GUI task continuously. Prefer {contract_path: absolute local JSON path}; legacy inline contracts also work. Strict local schema and permissions are validated before actions. Chrome must use the skill's official-session gateway. Read skill references/protocol.md, not implementation files.",inputSchema=contract_input_schema()),
        types.Tool(name="resume_task",description="Long-poll an existing task, or resume the unchanged contract after local repair. Never expands authorization. No need for high-frequency polling.",inputSchema=Resume.model_json_schema()),
        types.Tool(name="cancel_task",description="Stop issuing GUI actions and reconcile any in-flight action before saving a terminal checkpoint.",inputSchema=Cancel.model_json_schema()),
        types.Tool(name="diagnose_task",description="Return capabilities or an on-demand compact checkpoint; raw private UI state stays local.",inputSchema=Diagnose.model_json_schema())])
    if not gui.enabled():result.tools=[t for t in result.tools if t.name not in gui.TOOLS]
    return result

async def call_tool(ctx, params):
    try:
        if params.name in gui.TOOLS and gui.enabled():
            result=await getattr(gui,params.name)(params.arguments or {})
        elif params.name == "evaluate":
            result = await JevClient().evaluate(params.arguments or {})
        elif params.name in ("health", "capabilities") and not params.arguments:
            result = health() if params.name == "health" else capabilities()
            if params.name=="capabilities":
                result.update(gui_execution=gui.enabled(),gui_scope="bounded task controller; evaluate itself is decision-only",
                    calibration_required_before_autonomous_actions="Domain calibration remains required before broader semantic autonomy; low-risk fixture thresholds are uncalibrated engineering values.",gui_delegate=gui.capabilities())
        else:
            raise BridgeError("INVALID_TOOL_OR_ARGUMENTS")
    except BridgeError as exc:
        result = {"ok":False, "error":exc.code, "attempts":exc.attempts}
    except Stop as exc:
        result={"ok":False,"status":exc.status,"error":exc.reason}
    except ValidationError:
        result={"ok":False,"status":"blocked","error":"INVALID_TASK_SCHEMA"}
    except Exception:
        result = {"ok":False, "error":"INTERNAL_ERROR"}
    return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))],
        structuredContent=result, isError=result.get("ok") is False)

async def main():
    server = Server("jev-bridge", version="1.0.0", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
