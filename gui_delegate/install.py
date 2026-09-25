"""Repeatable user-level install/rollback; preserve every unrelated setting."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import tomlkit
from jev_client import ROOT
from manage import codex_home,backup
from .schema import Contract,Observation,Action,Checkpoint,Result,Resume,Cancel,Diagnose
from .service import TOOLS

BASE=ROOT/"gui_delegate";STATE=BASE/"install-state.json"
START="<!-- jev-gui-delegate:begin -->";END="<!-- jev-gui-delegate:end -->"
ROUTE="""<!-- jev-gui-delegate:begin -->
所有 GUI 优先使用用户 skill `jev-gui-delegate`，不按网站、应用、控件类型或任务长度排除。目标是减少 Astra 的观察、判断和逐步操作；完整子流程尽量一次委派，确定性动作由本地控制器执行，语义判断用 Jev，不强行增加模型调用。网页走 references/chrome.md 的 chrome_gateway.mjs；原生桌面走 jev-bridge.run_task，MCP 未加载用同一 CLI。非 GUI 工作优先可靠 API/CLI。
低置信、缺文本、控件失配或临时故障先用局部补充、已有恢复或有依据的修复继续委派；不因一次失败直接接管，也不重复无进展尝试。当前能力或诊断确认执行器无法完成所需部分（含合理修复仍不可用）后，Astra 才局部接手，随后可执行步骤回到 Jev。无需故意失败、grant、bind-fallback、调用绑定或 120 秒令牌。分段、步数、预算和标签数不是改用 Astra 的理由。
优先精简结果和执行器局部观察；completed 且验证通过即可交付，不重复读屏。模型、阈值、候选覆盖、实时身份和后置验证不因省 token 削弱。Hook 非拦截且不增加审批；现有用户授权、系统／工具权限、用户接管和急停有效，不重放结果不明的动作。控制器执行、真实 Jev 请求与 Astra 补充／接手分别记录；零模型调用如实报告。
<!-- jev-gui-delegate:end -->"""

def install():
    home=codex_home();skill=Path.home()/".agents/skills/jev-gui-delegate"
    config=home/"config.toml";hooks=home/"hooks.json"
    if any(ch.isspace() for ch in str(ROOT)):raise RuntimeError("This reviewed Windows hook launcher requires the recorded project path without spaces")
    global_rules=home/("AGENTS.override.md" if (home/"AGENTS.override.md").exists() else "AGENTS.md")
    state=json.loads(STATE.read_text("utf-8")) if STATE.exists() else {}
    if state.get("active"):
        assert skill.is_dir(),"installed skill missing"
        return {"installed":True,"changed":False,"skill":str(skill)}
    if skill.exists():raise RuntimeError("Existing unrelated skill preserved; inspect before adoption")
    originals={str(p):backup(p) if p.exists() else None for p in (config,hooks,global_rules)}
    doc=tomlkit.parse(config.read_text("utf-8"));original=doc.unwrap()
    entry=doc["mcp_servers"]["jev-bridge"]
    if str(ROOT/"server.py") not in entry["args"]:raise RuntimeError("Jev registration identity mismatch")
    old_tools=list(entry.get("enabled_tools",[]))
    entry["enabled_tools"]=list(dict.fromkeys(old_tools+list(TOOLS)))
    modified=doc.unwrap();modified["mcp_servers"]["jev-bridge"]["enabled_tools"]=old_tools
    assert modified==original,"unrelated config would change"
    hook_entry={"matcher":"^(mcp__cua_repl[._]+js|mcp__node_repl[._]+js|cua_repl[.]js|node_repl[.]js|Bash)$","hooks":[{"type":"command",
      "command":(ROOT/".venv/Scripts/python.exe").as_posix()+" "+(BASE/"hook.py").as_posix(),
      "timeout":5,"statusMessage":"Jev GUI delegation route"}]}
    hook_doc=json.loads(hooks.read_text("utf-8")) if hooks.exists() else {}
    pre=hook_doc.setdefault("hooks",{}).setdefault("PreToolUse",[])
    if hook_entry not in pre:pre.append(hook_entry)
    rules=global_rules.read_text("utf-8") if global_rules.exists() else ""
    if START in rules:raise RuntimeError("Unowned route marker preserved")
    shutil.copytree(BASE/"skill",skill,copy_function=shutil.copyfile)
    config.write_text(tomlkit.dumps(doc),"utf-8")
    hooks.write_text(json.dumps(hook_doc,ensure_ascii=False,indent=2),"utf-8")
    global_rules.write_text(rules.rstrip()+"\n\n"+ROUTE+"\n","utf-8")
    state={"active":True,"skill":str(skill),"rules":str(global_rules),"config":str(config),"hooks":str(hooks),
       "backups":originals,"original_enabled_tools":old_tools,"hook_entry":hook_entry,
       "skill_hashes":{str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in skill.rglob('*') if p.is_file()}}
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),"utf-8")
    registration=ROOT/"reports/registration.json"
    if registration.exists():
        backup(registration);record=json.loads(registration.read_text("utf-8"));record["entry"]=doc.unwrap()["mcp_servers"]["jev-bridge"]
        registration.write_text(json.dumps(record,ensure_ascii=False,indent=2),"utf-8")
    schemas=BASE/"schemas";schemas.mkdir(exist_ok=True)
    for model in (Contract,Observation,Action,Checkpoint,Result,Resume,Cancel,Diagnose):
        (schemas/(model.__name__.lower()+".json")).write_text(json.dumps(model.model_json_schema(),ensure_ascii=False,indent=2),"utf-8")
    from .examples import workflow
    examples=BASE/"examples";examples.mkdir(exist_ok=True)
    (examples/"workflow.json").write_text(json.dumps(workflow(),ensure_ascii=False,indent=2),"utf-8")
    manifest=home/"jev-integration.json";backup(manifest)
    data=json.loads(manifest.read_text("utf-8"))
    data["gui_delegate"]={"version":"0.4.3","project":str(BASE),"skill":str(skill),"entry":"python -m gui_delegate.cli",
        "mcp_tools":list(TOOLS),"schemas":str(schemas),"reports":str(BASE/"reports"),"support_matrix":str(BASE/"SUPPORT.md"),
        "global_rules":str(global_rules),"hook_status":"REGISTERED_REQUIRES_NORMAL_TRUST_VERIFICATION","new_session_required":True,
        "emergency_stop":str(ROOT/"gui-stop.cmd"),"rollback":str(ROOT/"gui-uninstall.cmd"),"thresholds_calibrated":False}
    data["new_conversation_required"]=True
    manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),"utf-8")
    return {"installed":True,"changed":True,"skill":str(skill),"rules":str(global_rules),"hook":"registered; trust status not yet verified"}

def rollback():
    if not STATE.exists():return {"removed":True,"changed":False}
    state=json.loads(STATE.read_text("utf-8"))
    if not state.get("active"):return {"removed":True,"changed":False}
    skill=Path(state["skill"]).resolve()
    if skill!= (Path.home()/".agents/skills/jev-gui-delegate").resolve():raise RuntimeError("Rollback path denied")
    current={str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in skill.rglob('*') if p.is_file()}
    if current!=state["skill_hashes"]:raise RuntimeError("Skill changed; preserve user edits")
    if ROUTE not in Path(state["rules"]).read_text("utf-8"):raise RuntimeError("Route edited; preserve user changes")
    for name in ("config","hooks","rules"):backup(Path(state[name]))
    config=Path(state["config"]);doc=tomlkit.parse(config.read_text("utf-8"))
    entry=doc.get("mcp_servers",{}).get("jev-bridge")
    if entry is not None:entry["enabled_tools"]=[x for x in entry.get("enabled_tools",[]) if x not in TOOLS]
    config.write_text(tomlkit.dumps(doc),"utf-8")
    hooks=Path(state["hooks"]);h=json.loads(hooks.read_text("utf-8"));pre=h.get("hooks",{}).get("PreToolUse",[])
    h["hooks"]["PreToolUse"]=[x for x in pre if x!=state["hook_entry"]]
    hooks.write_text(json.dumps(h,ensure_ascii=False,indent=2),"utf-8")
    rules=Path(state["rules"]);s=rules.read_text("utf-8")
    if ROUTE not in s:raise RuntimeError("Route edited; preserve user changes")
    rules.write_text(s.replace("\n\n"+ROUTE+"\n","\n"),"utf-8")
    shutil.rmtree(skill)
    state["active"]=False;STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),"utf-8")
    registration=ROOT/"reports/registration.json";r=json.loads(registration.read_text("utf-8"));r["entry"]=entry.unwrap() if entry is not None else r["entry"]
    registration.write_text(json.dumps(r,ensure_ascii=False,indent=2),"utf-8")
    manifest=codex_home()/"jev-integration.json";data=json.loads(manifest.read_text("utf-8"))
    data["gui_delegate"]["registration"]="removed";manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),"utf-8")
    return {"removed":True,"source_and_credentials_retained":True}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("action",choices=["install","rollback"]);args=p.parse_args()
    print(json.dumps(install() if args.action=="install" else rollback(),ensure_ascii=True,indent=2))

