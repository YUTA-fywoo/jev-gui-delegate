"""GUI routing hook; advisory by default, with legacy strict-mode support."""
import hashlib
import json
import re
import sys
import time
from pathlib import Path
if __package__ in (None,""):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gui_delegate import storage
from gui_delegate.security import Stop
from gui_delegate.fallback_policy import valid_grant
from gui_delegate import routing_policy

DIRECT_TOOLS={"mcp__cua_repl__js","mcp__node_repl__js","mcp__cua_repl.js","mcp__node_repl.js","cua_repl.js","node_repl.js","Bash"}
GUI_CODE=re.compile(r"(?:cua\.|@oai/sky|import\s+(?:playwright|pywinauto)|from\s+(?:playwright|pywinauto)|import\(['\"]playwright|\.getByRole\(|\.get_by_role\(|\.click\(|\.fill\(|\.type_keys\(|\.press\()")
BASH_GUI_IMPORT=re.compile(r"(?:\bfrom\s+(?:playwright|pywinauto|pyautogui|pynput)\b|\bimport\s+(?:playwright|pywinauto|pyautogui|pynput)\b|\b(?:import|require)\s*\(['\"](?:playwright|puppeteer|@oai/sky)['\"])")
TOKEN=re.compile(r"jev-fallback:([a-f0-9]{64})")
CUA_TOOLS={'mcp__cua_repl__js','mcp__cua_repl.js','cua_repl.js'}
# Dedicated GUI surface is default-deny. Aliases such as t.goto/export/evaluate
# cannot bypass routing merely by omitting the old click/fill keywords.
GATEWAY_SETUP=re.compile(r'''\s*(?:let )?jevStrictGateway = await import\("file:///C:/jev/jev-bridge/gui_delegate/chrome_gateway\.mjs\?release=0\.4\.[123]"\);?\s*''')
GATEWAY=re.compile(r'''\s*await jevStrictGateway\.dispatch\(\{browser:([A-Za-z_$][\w$]*),request:(.+)\},nodeRepl\);?\s*''',re.S)

def gateway_call(code):
    match=GATEWAY.fullmatch(code)
    if not match:return False
    try:
        request=json.loads(match.group(2))
        if not isinstance(request,dict):return False
        if request.get('operation')=='run_task':
            return set(request)=={'operation','contract_path'} and isinstance(request['contract_path'],str)
        return request.get('operation') in {'resume_task','cancel_task','diagnose_task','close_created_tab'} and set(request)=={'operation','arguments'} and isinstance(request['arguments'],dict)
    except (ValueError,TypeError):return False
# Read-only browser discovery is preparation for task delegation, not a direct
# GUI action. Full-match only: no extra calls, expressions or executable args.
READONLY_DISCOVERY=re.compile(r'''\s*(?:(?:let|const|var)\s+[A-Za-z_$][\w$]*\s*=\s*)?await\s+cua\.(?:(?:getState|listBrowsers|rewriteDocumentation)\(\s*\)|getBrowser\(\s*\{\s*id\s*:\s*(?:"[A-Za-z0-9_-]+"|'[A-Za-z0-9_-]+')\s*\}\s*\))\s*;?\s*''')

def code_hash(arguments):
    return hashlib.sha256(json.dumps(arguments,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

def decide(event):
    if routing_policy.preference_only():return {}
    tool=event.get("tool_name","");args=event.get("tool_input",{})
    if tool not in DIRECT_TOOLS or not isinstance(args,dict):return {}
    code=args.get("code",args.get("command",args.get("cmd","")))
    if isinstance(code,list):code=" ".join(code)
    if tool in CUA_TOOLS and isinstance(code,str) and (READONLY_DISCOVERY.fullmatch(code) or GATEWAY_SETUP.fullmatch(code) or gateway_call(code)):return {}
    pattern=BASH_GUI_IMPORT if tool=='Bash' else GUI_CODE
    if tool not in CUA_TOOLS and (not isinstance(code,str) or not pattern.search(code)):return {}
    if not isinstance(code,str):code=''
    match=TOKEN.search(code)
    if match:
        try:
            directory=storage.task_directory(match.group(1));grant=storage.read(directory/"fallback.dpapi")
            binding=storage.read(directory/"fallback-binding.dpapi")
            if (valid_grant(grant,directory) and not binding.get("used",False) and time.time()<min(grant["expires_at"],binding["expires_at"]) and binding["session_id"]==event.get("session_id")
                and binding["tool"]==tool and binding["arguments_sha256"]==code_hash(args)
                and binding["scope_hash"]==grant["scope_hash"]):
                binding["used"]=True;storage.save(directory/"fallback-binding.dpapi",binding)
                storage.event(directory,"fallback_used",tool=tool,reason=grant["reason"],scope_hash=grant["scope_hash"])
                return {}
        except (Stop,KeyError):pass
    return {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",
      "permissionDecisionReason":"JEV_GUI_ROUTE: Direct GUI calls are disabled. Do not repeat. Use the exact chrome_gateway.mjs dispatch call in jev-gui-delegate/references/chrome.md, or native jev-bridge.run_task. Low confidence, missing text and temporary errors require repair/resume through the executor. Only a runtime-verified capability gap permits a scoped, exact-call, session-bound fallback. Ordinary shell/non-GUI tools are unaffected."}}

def bind(token,session_id,tool,arguments):
    directory=storage.task_directory(token);grant=storage.read(directory/"fallback.dpapi")
    if not valid_grant(grant,directory) or tool not in DIRECT_TOOLS or tool not in grant.get("allowed_tools",[grant.get("allowed_tool")]) or not session_id or time.time()>=grant["expires_at"]:raise Stop("FALLBACK_GRANT_INVALID","blocked")
    if f"jev-fallback:{token}" not in str(arguments.get("code",arguments.get("cmd",arguments.get("command","")))):raise Stop("FALLBACK_TAG_REQUIRED","blocked")
    value={"session_id":session_id,"tool":tool,"arguments_sha256":code_hash(arguments),"scope_hash":grant["scope_hash"],
        "expires_at":min(grant["expires_at"],time.time()+120),"reason":grant["reason"]}
    storage.save(directory/"fallback-binding.dpapi",value)
    storage.event(directory,"fallback_bound",tool=tool,scope_hash=grant["scope_hash"],expires_at=value["expires_at"])
    return {"bound":True,"expires_at":value["expires_at"],"scope":grant["scope"],"reason":grant["reason"]}

if __name__=="__main__":
    try:
        # The host may retain stdin while waiting for stdout. Decode one complete JSON value
        # without waiting for EOF (which would turn this into a 5-second hook timeout).
        import os
        raw=b""
        while len(raw)<1024*1024:
            chunk=os.read(sys.stdin.fileno(),65536)
            if not chunk:break
            raw+=chunk
            try:event=json.loads(raw);break
            except (ValueError,UnicodeDecodeError):continue
        else:raise ValueError("hook input too large")
        event=json.loads(raw)
        decision=decide(event)
        storage.protect_directory(storage.DATA)
        storage.event(storage.DATA,"hook_checked",tool=event.get("tool_name","unknown"),session_id=event.get("session_id",""),decision="deny" if decision else "pass")
        print(json.dumps(decision,ensure_ascii=True))
    except Exception:
        # A failing guard never emits raw tool args or secrets.
        if routing_policy.preference_only():print("{}")
        else:print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"JEV_GUI_ROUTE_GUARD_FAILED: inspect local runtime; do not retry the same direct GUI call."}}))
