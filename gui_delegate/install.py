"""Repeatable user-level install/rollback; preserve every unrelated setting."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
import tomlkit
from jev_client import ROOT
from manage import codex_home,backup,installation_context,desired as desired_mcp
from .schema import Contract,Observation,Action,Checkpoint,Result,Resume,Cancel,Diagnose
from .service import TOOLS

BASE=ROOT/"gui_delegate";STATE=BASE/"install-state.json"
START="<!-- jev-gui-delegate:begin -->";END="<!-- jev-gui-delegate:end -->"
VERSION='0.7.0'

def skill_files():
    files={}
    for path in (BASE/'skill').rglob('*'):
        if not path.is_file():continue
        content=path.read_bytes()
        if path.suffix in ('.md','.json','.yaml','.yml'):
            text=content.decode('utf-8').replace('file:///C:/jev/jev-bridge',ROOT.as_uri())
            text=text.replace('C:/jev/jev-bridge',ROOT.as_posix()).replace('C:\\jev\\jev-bridge',str(ROOT))
            content=text.encode('utf-8')
        files[str(path.relative_to(BASE/'skill'))]=content
    return files
ROUTE="""<!-- jev-gui-delegate:begin -->
所有 GUI 优先使用用户 skill `jev-gui-delegate`，不按网站、应用、控件类型或任务长度排除。目标是减少 Astra 的观察、判断和逐步操作；完整子流程尽量一次委派，确定性动作由本地控制器执行，语义判断用 Jev，不强行增加模型调用。网页走 references/chrome.md 的 chrome_gateway.mjs；原生桌面走 jev-bridge.run_task，MCP 未加载用同一 CLI。非 GUI 工作优先可靠 API/CLI。
低置信、缺文本、控件失配或临时故障先用局部补充、已有恢复或有依据的修复继续委派；不因一次失败直接接管，也不重复无进展尝试。当前能力或诊断确认执行器无法完成所需部分（含合理修复仍不可用）后，Astra 才局部接手，随后可执行步骤回到 Jev。无需故意失败、grant、bind-fallback、调用绑定或 120 秒令牌。分段、步数、预算和标签数不是改用 Astra 的理由。
优先精简结果和执行器局部观察；completed 且验证通过即可交付，不重复读屏。模型、阈值、候选覆盖、实时身份和后置验证不因省 token 削弱。Hook 非拦截且不增加审批；现有用户授权、系统／工具权限、用户接管和急停有效，不重放结果不明的动作。控制器执行、真实 Jev 请求与 Astra 补充／接手分别记录；零模型调用如实报告。
<!-- jev-gui-delegate:end -->"""

def hook_definition():
    return {"matcher":"^(mcp__cua_repl[._]+js|mcp__node_repl[._]+js|cua_repl[.]js|node_repl[.]js|Bash)$","hooks":[{"type":"command",
        "command":subprocess.list2cmdline([str(ROOT/".venv/Scripts/python.exe"),str(BASE/"hook.py")]),
        "timeout":5,"statusMessage":"Jev GUI delegation route"}]}

def manifest_fields(skill,rules):
    return {"version":VERSION,"registration":"registered","project":str(BASE),"skill":str(skill),"entry":"python -m gui_delegate.cli",
        "gateway":str(BASE/'chrome_gateway.mjs'),"python":str(ROOT/'.venv/Scripts/python.exe'),
        "mcp_tools":list(TOOLS),"schemas":str(BASE/'schemas'),"reports":str(BASE/"reports"),"support_matrix":str(BASE/"SUPPORT.md"),
        "global_rules":str(rules),"hook_status":"REGISTERED_REQUIRES_NORMAL_TRUST_VERIFICATION","new_session_required":True,
        "emergency_stop":str(ROOT/"gui-stop.cmd"),"rollback":str(ROOT/"gui-uninstall.cmd"),"thresholds_calibrated":False}

def write_changed(path,content):
    """Back up only files that actually change; preserve unrelated content."""
    if path.exists():
        current=path.read_text('utf-8') if isinstance(content,str) else path.read_bytes()
        if current==content:return False
    if path.exists():backup(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(content,str):path.write_text(content,encoding='utf-8')
    else:path.write_bytes(content)
    return True

def support_files():
    from .examples import workflow
    files={BASE/'schemas'/(model.__name__.lower()+'.json'):json.dumps(model.model_json_schema(),ensure_ascii=False,indent=2)
        for model in (Contract,Observation,Action,Checkpoint,Result,Resume,Cancel,Diagnose)}
    files[BASE/'examples/workflow.json']=json.dumps(workflow(),ensure_ascii=False,indent=2)
    return files

def remove_owned_route(text,route):
    block='\n\n'+route+'\n'
    return text.replace(block,'',1) if block in text else text.replace(route,'',1)

def install():
    home=codex_home();skill=Path.home()/".agents/skills/jev-gui-delegate"
    config=home/"config.toml";hooks=home/"hooks.json"
    global_rules=home/("AGENTS.override.md" if (home/"AGENTS.override.md").exists() else "AGENTS.md")
    state=json.loads(STATE.read_text("utf-8")) if STATE.exists() else {}
    installation_context(state)
    if state.get("active"):
        assert skill.is_dir(),"installed skill missing"
        desired=skill_files()
        current={str(p.relative_to(skill)):p.read_bytes() for p in skill.rglob('*') if p.is_file()}
        hashes={name:hashlib.sha256(data).hexdigest() for name,data in current.items()}
        if current!=desired and hashes!=state.get('skill_hashes'):
            raise RuntimeError('Installed skill has local edits; preserved for review')
        if set(current)-set(desired):raise RuntimeError('Upgrade would remove local skill files; preserved for review')
        doc=tomlkit.parse(config.read_text('utf-8'))
        entry=doc.unwrap().get('mcp_servers',{}).get('jev-bridge')
        if entry!=desired_mcp():
            raise RuntimeError('MCP registration missing or changed; run install-skill.cmd to review the owned registration')
        hook_doc=json.loads(hooks.read_text('utf-8'))
        pre=hook_doc.get('hooks',{}).get('PreToolUse',[])
        old_hook=state.get('hook_entry')
        if pre.count(old_hook)!=1:
            raise RuntimeError('Owned Hook missing or changed; user configuration preserved')
        hook_entry=hook_definition()
        pre[pre.index(old_hook)]=hook_entry
        old_rules=Path(state['rules']);old_route=state.get('route',ROUTE)
        rules=old_rules.read_text('utf-8')
        if rules.count(old_route)!=1:
            raise RuntimeError('Owned route missing or edited; user rules preserved')
        changes={}
        if old_rules.resolve()!=global_rules.resolve():
            new_rules=global_rules.read_text('utf-8') if global_rules.exists() else ''
            if START in new_rules or END in new_rules:
                raise RuntimeError('Unowned route marker in active rules; user rules preserved')
            changes[old_rules]=remove_owned_route(rules,old_route)
            changes[global_rules]=new_rules+'\n\n'+ROUTE+'\n'
        else:
            changes[global_rules]=rules.replace(old_route,ROUTE,1)
        manifest=home/'jev-integration.json'
        data=json.loads(manifest.read_text('utf-8')) if manifest.exists() else {}
        data.setdefault('schema_version',1);data['project_path']=str(ROOT)
        data.setdefault('gui_delegate',{}).update(manifest_fields(skill,global_rules))
        data['new_conversation_required']=True
        state.update(skill_hashes={name:hashlib.sha256(content).hexdigest() for name,content in desired.items()},
            version=VERSION,project_path=str(ROOT),rules=str(global_rules),route=ROUTE,hook_entry=hook_entry)
        changes.update({skill/name:content for name,content in desired.items()})
        changes.update(support_files())
        changes[hooks]=json.dumps(hook_doc,ensure_ascii=False,indent=2)
        changes[manifest]=json.dumps(data,ensure_ascii=False,indent=2)
        changes[STATE]=json.dumps(state,ensure_ascii=False,indent=2)
        changed=False
        for path,content in changes.items():
            changed=write_changed(path,content) or changed
        return {"installed":True,"changed":changed,"skill":str(skill),"version":VERSION}
    if skill.exists():raise RuntimeError("Existing unrelated skill preserved; inspect before adoption")
    doc=tomlkit.parse(config.read_text("utf-8"));original=doc.unwrap()
    entry=doc["mcp_servers"]["jev-bridge"]
    if str(ROOT/"server.py") not in entry["args"]:raise RuntimeError("Jev registration identity mismatch")
    registration=ROOT/'reports/registration.json'
    record=json.loads(registration.read_text('utf-8')) if registration.exists() else {}
    if (record.get('created_by_this_installation') is not True or record.get('entry')!=entry.unwrap()
            or Path(record.get('config','')).resolve()!=config.resolve()):
        raise RuntimeError('REGISTRATION_OWNERSHIP_MISSING: existing MCP configuration preserved')
    old_tools=list(entry.get("enabled_tools",[]))
    entry["enabled_tools"]=list(dict.fromkeys(old_tools+list(TOOLS)))
    modified=doc.unwrap();modified["mcp_servers"]["jev-bridge"]["enabled_tools"]=old_tools
    assert modified==original,"unrelated config would change"
    hook_entry=hook_definition()
    hook_doc=json.loads(hooks.read_text("utf-8")) if hooks.exists() else {}
    pre=hook_doc.setdefault("hooks",{}).setdefault("PreToolUse",[])
    if hook_entry in pre:raise RuntimeError('Unowned Hook preserved; installation record is unavailable')
    pre.append(hook_entry)
    rules=global_rules.read_text("utf-8") if global_rules.exists() else ""
    if START in rules or END in rules:raise RuntimeError("Unowned route marker preserved")
    manifest=home/'jev-integration.json'
    data=json.loads(manifest.read_text('utf-8')) if manifest.exists() else {'schema_version':1,'project_path':str(ROOT)}
    data.setdefault('gui_delegate',{}).update(manifest_fields(skill,global_rules))
    data['new_conversation_required']=True
    generated=support_files()
    originals={str(p):backup(p) if p.exists() else None for p in (config,hooks,global_rules)}
    for name,content in skill_files().items():
        path=skill/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    config.write_text(tomlkit.dumps(doc),"utf-8")
    hooks.write_text(json.dumps(hook_doc,ensure_ascii=False,indent=2),"utf-8")
    global_rules.write_text(rules+"\n\n"+ROUTE+"\n","utf-8")
    state={"active":True,"version":VERSION,"project_path":str(ROOT),"route":ROUTE,
       "skill":str(skill),"rules":str(global_rules),"config":str(config),"hooks":str(hooks),
       "backups":originals,"original_enabled_tools":old_tools,"hook_entry":hook_entry,
       "skill_hashes":{str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in skill.rglob('*') if p.is_file()}}
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),"utf-8")
    backup(registration);record["entry"]=doc.unwrap()["mcp_servers"]["jev-bridge"]
    registration.write_text(json.dumps(record,ensure_ascii=False,indent=2),"utf-8")
    for path,content in generated.items():write_changed(path,content)
    write_changed(manifest,json.dumps(data,ensure_ascii=False,indent=2))
    return {"installed":True,"changed":True,"skill":str(skill),"rules":str(global_rules),"hook":"registered; trust status not yet verified"}

def rollback():
    if not STATE.exists():return {"removed":True,"changed":False}
    state=json.loads(STATE.read_text("utf-8"))
    if not state.get("active"):return {"removed":True,"changed":False}
    installation_context(state)
    skill=Path(state["skill"]).resolve()
    if skill!= (Path.home()/".agents/skills/jev-gui-delegate").resolve():raise RuntimeError("Rollback path denied")
    current={str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in skill.rglob('*') if p.is_file()}
    if current!=state["skill_hashes"]:raise RuntimeError("Skill changed; preserve user edits")
    route=state.get('route',ROUTE)
    if route not in Path(state["rules"]).read_text("utf-8"):raise RuntimeError("Route edited; preserve user changes")
    for name in ("config","hooks","rules"):backup(Path(state[name]))
    config=Path(state["config"]);doc=tomlkit.parse(config.read_text("utf-8"))
    entry=doc.get("mcp_servers",{}).get("jev-bridge")
    if entry is not None:entry["enabled_tools"]=[x for x in entry.get("enabled_tools",[]) if x not in TOOLS]
    config.write_text(tomlkit.dumps(doc),"utf-8")
    hooks=Path(state["hooks"]);h=json.loads(hooks.read_text("utf-8"));pre=h.get("hooks",{}).get("PreToolUse",[])
    h["hooks"]["PreToolUse"]=[x for x in pre if x!=state["hook_entry"]]
    hooks.write_text(json.dumps(h,ensure_ascii=False,indent=2),"utf-8")
    rules=Path(state["rules"]);s=rules.read_text("utf-8")
    if route not in s:raise RuntimeError("Route edited; preserve user changes")
    rules.write_text(remove_owned_route(s,route),"utf-8")
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

