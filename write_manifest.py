import datetime
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import ctypes
from pathlib import Path
from jev_client import ROOT,load_settings,statistics
from credentials import resolve_key,TARGET
from manage import codex_home

def read_report(name):
    path=ROOT/"reports"/name
    return json.loads(path.read_text("utf-8")) if path.exists() else {"status":"NOT_RUN"}

def write_manifest():
    direct=read_report("direct-test.json")
    mcp=read_report("mcp-test.json")
    gui=read_report("gui-test.json")
    codex=read_report("codex-test.json")
    current=read_report("current-session-test.json")
    key,source=resolve_key()
    versions={n:importlib.metadata.version(n) for n in ("typesafe-sdk","mcp","playwright","pywinauto","pywin32","tomlkit")}
    model=direct.get("result",{}).get("model") or mcp.get("live_evaluate",{}).get("result",{}).get("model")
    tests={"direct_jev_api":direct.get("status","NOT_RUN"),
        "mcp_tools_list":mcp.get("tools_list",{}).get("status","NOT_RUN"),
        "mcp_tools_call":mcp.get("health",{}).get("status","NOT_RUN"),
        "mcp_environment_forwarding":read_report("mcp-environment-test.json").get("status","NOT_RUN"),
        "windows_credential_storage":read_report("credential-tests.json").get("status","NOT_RUN"),
        "mcp_authenticated_jev":mcp.get("live_evaluate",{}).get("status","NOT_RUN"),
        "codex_active_mcp_authenticated_jev":current.get("status","NOT_RUN"),
        "browser_semantic_state":gui.get("browser",{}).get("status","NOT_RUN"),
        "windows_uia_and_input":gui.get("windows_uia",{}).get("status","NOT_RUN"),
        "controlled_failures":read_report("failure-tests.json").get("status","NOT_RUN"),
        "config_rollback":read_report("registration-tests.json").get("status","NOT_RUN"),
        "codex_skill_discovery":codex.get("official_skill",{}).get("status","NOT_RUN"),
        "fresh_codex_mcp_discovery":codex.get("fresh_codex_mcp_inventory",{}).get("status","NOT_RUN")}
    todos=[]
    if tests["direct_jev_api"]!="PASS" or tests["mcp_authenticated_jev"]!="PASS":
        todos.append("Save a TypeSafe key via set-key.cmd, then run verify.cmd to perform real direct and MCP Choice/Noul/Score calls.")
    if current.get("status")!="PASS":
        todos.append("Open a new Codex conversation to obtain the newly registered MCP tools in its active tool catalog.")
    todos.extend([
        "Before autonomous GUI execution, build a bounded executor and calibrate domain-specific thresholds against the observed version; pin that version using manage.py pin.",
        "Canvas/image-only/remote desktops and elevated/secure desktops need a separately approved state/execution strategy. No OCR or local generative model installed."])
    session_id=ctypes.c_ulong()
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(),ctypes.byref(session_id))
    manifest={"schema_version":1,"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "project_path":str(ROOT),"runtime":{"os":platform.platform(),"native_windows":True,"wsl":False,
        "python_executable":sys.executable,"python_version":platform.python_version(),"python_base":sys.base_prefix,
        "interactive_session_id":session_id.value,"codex_client":"local Windows Codex desktop with bundled CLI",
        "codex_version":"0.155.0-alpha.16","node_version":"24.19.0","versions":versions},
        "mcp_name":"jev-bridge","mcp_origin":"locally built; not a TypeSafe vendor MCP package",
        "registration":"registered","transport":"stdio","config_path":str(codex_home()/"config.toml"),
        "registration_backup":read_report("registration.json").get("backup"),
        "main_model_preserved":True,"login_and_provider_preserved":True,
        "skill_path":str(Path.home()/".agents/skills/typesafe-ai/SKILL.md"),
        "credential":{"configured":bool(key),"source":source,"target_name":TARGET,
            "environment_variable":"TYPESAFE_API_KEY","mcp_authentication_verified":tests["mcp_authenticated_jev"]=="PASS"},
        "api":{"endpoint":"https://api.typesafe.ai/v1/systemone","settings":load_settings().model_dump(),
            "actual_model_version":model,"usage":statistics(),"cost_accounting":"Reported token totals only; no monetary estimate. Timed-out attempts may still be billed."},
        "drivers":{"browser":gui.get("browser",{}),"windows":gui.get("windows_uia",{})},
        "tests":tests,"reports_directory":str(ROOT/"reports"),
        "current_conversation_tools":"loaded and real evaluate verified in recorded thread" if current.get("status")=="PASS" else "not verified",
        "verified_thread_id":current.get("thread_id"),
        "new_conversation_required":current.get("status")!="PASS",
        "fresh_codex_process_tools":tests["fresh_codex_mcp_discovery"],
        "gui_control_delegated_to_jev":False,"todo":todos,
        "commands":{"health":str(ROOT/"health.cmd"),"real_verification":str(ROOT/"verify.cmd"),
            "credential_input":str(ROOT/"set-key.cmd"),"uninstall":str(ROOT/"uninstall.cmd")}}
    path=codex_home()/"jev-integration.json"
    if path.exists():
        previous=json.loads(path.read_text("utf-8"))
        if "gui_delegate" in previous:
            manifest["gui_delegate"]=previous["gui_delegate"]
            manifest["drivers"]=previous.get("drivers",manifest["drivers"])
            manifest["gui_control_delegated_to_jev"]=previous.get("gui_control_delegated_to_jev",False)
            manifest["new_conversation_required"]=previous.get("new_conversation_required",True)
            manifest["todo"]=previous.get("todo",todos)
            for key in ("gui_delegation_scope","all_gui_takeover"):
                if key in previous:manifest[key]=previous[key]
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (ROOT/"reports/acceptance.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return path

if __name__=="__main__":print(write_manifest())
