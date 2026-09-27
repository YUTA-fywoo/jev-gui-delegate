"""Idempotent registration and narrowly scoped rollback; never read Codex auth."""
import argparse
import datetime
import json
import os
import re
import shutil
from pathlib import Path
import tomlkit
from jev_client import ROOT, database, load_settings

def codex_home():
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()

def backup(path):
    directory = codex_home() / "backups/jev-bridge"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dest = directory / (path.name + "." + stamp + ".bak")
    shutil.copyfile(path, dest)
    return str(dest)

def installation_context(state=None):
    """Reject copying an owned installation to another root, user or Codex home."""
    state_path=ROOT/"gui_delegate/install-state.json"
    if state is None:
        state=json.loads(state_path.read_text("utf-8")) if state_path.exists() else {}
    if not state.get("active"):
        return
    expected={"config":codex_home()/"config.toml", "hooks":codex_home()/"hooks.json",
        "skill":Path.home()/".agents/skills/jev-gui-delegate"}
    for name,path in expected.items():
        if not state.get(name) or Path(state[name]).resolve()!=path.resolve():
            raise RuntimeError("INSTALL_LOCATION_CHANGED: restore the original CODEX_HOME, user and project directory before reinstalling")
    if Path(state.get("rules", "")).resolve().parent!=codex_home().resolve():
        raise RuntimeError("INSTALL_LOCATION_CHANGED: global rules belong to another CODEX_HOME")
    if state.get("project_path") and Path(state["project_path"]).resolve()!=ROOT.resolve():
        raise RuntimeError("INSTALL_LOCATION_CHANGED: project directory moved; existing configuration preserved")
    record_path=ROOT/"reports/registration.json"
    if not record_path.exists():
        raise RuntimeError("REGISTRATION_OWNERSHIP_MISSING: registration record is required to upgrade this installation")
    record=json.loads(record_path.read_text("utf-8"))
    entry=record.get("entry",{})
    if (Path(record.get("config", "")).resolve()!=(codex_home()/"config.toml").resolve()
            or str(ROOT/"server.py") not in entry.get("args",[])
            or Path(entry.get("command", "")).resolve()!=(ROOT/".venv/Scripts/python.exe").resolve()):
        raise RuntimeError("INSTALL_LOCATION_CHANGED: registration belongs to another location; configuration preserved")

def desired():
    tools=["health", "capabilities", "evaluate"]
    state=ROOT/"gui_delegate/install-state.json"
    if state.exists() and json.loads(state.read_text("utf-8")).get("active"):
        from gui_delegate.service import TOOLS
        tools+=list(TOOLS)
    return {"command":str(ROOT / ".venv/Scripts/python.exe"),
        "args":["-u", str(ROOT / "server.py")], "cwd":str(ROOT),
        "env_vars":["TYPESAFE_API_KEY"],
        "env":{"PYTHONUTF8":"1", "TYPESAFE_LOG_LEVEL":"off"},
        "startup_timeout_sec":15, "tool_timeout_sec":55,
        "enabled_tools":tools}

def register():
    installation_context()
    path = codex_home() / "config.toml"
    path.parent.mkdir(parents=True,exist_ok=True)
    doc = tomlkit.parse(path.read_text("utf-8")) if path.exists() else tomlkit.document()
    original = doc.unwrap()
    existing = original.get("mcp_servers",{}).get("jev-bridge")
    report_path = ROOT / "reports/registration.json"
    report = json.loads(report_path.read_text("utf-8")) if report_path.exists() else {}
    owned=(report.get("created_by_this_installation") is True
        and Path(report.get("config", "")).resolve()==path.resolve()
        and report.get("entry")==existing)
    if existing is not None and not report:
        raise RuntimeError("REGISTRATION_OWNERSHIP_MISSING: matching existing entry preserved; installation record is unavailable")
    if existing is not None and not owned:
        raise RuntimeError("MCP_NAME_CONFLICT: existing entry preserved")
    if owned and (Path(existing.get("command", "")).resolve()!=(ROOT/".venv/Scripts/python.exe").resolve()
            or str(ROOT/"server.py") not in existing.get("args",[])):
        raise RuntimeError("INSTALL_LOCATION_CHANGED: registered project directory moved; existing entry preserved")
    changed=existing!=desired()
    if changed:
        saved = backup(path) if path.exists() else None
        if "mcp_servers" not in doc:
            doc["mcp_servers"] = tomlkit.table()
        doc["mcp_servers"]["jev-bridge"] = desired()
        candidate = tomlkit.dumps(doc)
        parsed = tomlkit.parse(candidate).unwrap()
        if existing is None:
            del parsed["mcp_servers"]["jev-bridge"]
            if "mcp_servers" not in original and not parsed["mcp_servers"]:
                del parsed["mcp_servers"]
        else:
            parsed["mcp_servers"]["jev-bridge"]=existing
        assert parsed == original, "unrelated config changed"
        path.write_text(candidate, encoding="utf-8")
        report = {"config":str(path), "backup":saved, "mcp_name":"jev-bridge",
            "entry":desired(), "created_by_this_installation":True,
            "unrelated_config_preserved":True}
        report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"registered":True,"config":str(path),"changed":changed},ensure_ascii=False))

def rollback(delete_credential=False):
    installation_context()
    path = codex_home() / "config.toml"
    doc = tomlkit.parse(path.read_text("utf-8"))
    entry = doc.get("mcp_servers",{}).get("jev-bridge")
    report = json.loads((ROOT / "reports/registration.json").read_text("utf-8"))
    if entry is not None:
        if entry.unwrap() != report["entry"] or not report["created_by_this_installation"]:
            raise RuntimeError("Entry changed since installation; preserved for review")
        backup(path)
        del doc["mcp_servers"]["jev-bridge"]
        path.write_text(tomlkit.dumps(doc),encoding="utf-8")
    if delete_credential:
        from credentials import remove_key
        remove_key()
    manifest = codex_home()/"jev-integration.json"
    if manifest.exists():
        data=json.loads(manifest.read_text("utf-8"))
        data["registration"]="removed"
        manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Jev MCP entry removed. Source and shared dependencies retained.")

def pin_model(model):
    if not re.fullmatch(r"jev-\d+\.\d+\.\d+",model):
        raise RuntimeError("A versioned Jev model ID is required")
    with database() as con:
        if not con.execute("SELECT 1 FROM calls WHERE model=?",(model,)).fetchone():
            raise RuntimeError("Model has not been observed in a real local response")
    settings=load_settings().model_dump()
    settings.update(model=model,expected_model=model,calibrated=False)
    path=ROOT/"settings.json"
    backup(path)
    path.write_text(json.dumps(settings,indent=2),encoding="utf-8")
    print("Model pinned; calibration remains false until separately validated.")

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["register","rollback","pin"])
    parser.add_argument("--delete-credential",action="store_true")
    parser.add_argument("--model")
    args=parser.parse_args()
    if args.action == "register": register()
    elif args.action == "rollback": rollback(args.delete_credential)
    else: pin_model(args.model or "")
