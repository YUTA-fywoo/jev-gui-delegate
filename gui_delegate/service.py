import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from jev_client import ROOT
from .schema import Contract,Resume,Cancel,Diagnose
from .security import Stop,validate_contract
from . import storage
from .routing_policy import describe as describe_routing_policy

TOOLS=("run_task","resume_task","cancel_task","diagnose_task")

def enabled():
    path=ROOT/"gui_delegate/install-state.json"
    try:return json.loads(path.read_text("utf-8")).get("active") is True
    except (OSError,ValueError):return False

def capabilities():
    from .decision_policy import load
    from .semantic_rule_policy import describe
    from .input_guard import describe as input_policy
    from .chrome_policy import describe as chrome_policy
    policy=load()
    from .chrome_session import OPS
    return {"version":"0.4.3","installed":enabled(),"drivers":["official Chrome DOM/open shadow/allowed frames/validated drag","Windows UIA patterns","named surfaces and local value transfer","clipboard HGLOBAL preservation"],
      "new_browser_profiles_only":False,"legacy_isolated_browser":"REMOVED; use official Chrome session or scoped Astra fallback","official_chrome":{**chrome_policy(),"supported_operations":sorted(OPS-{'dialog_accept','dialog_dismiss'}),"coverage_report":str(ROOT/'gui_delegate/reports/chrome-complete-20260923/REPORT.md'),"all_official_capabilities_autonomous":False,"blocked_operations":["JavaScript modal handling: current official host focus initialization times out","generic content.export: current Chrome backend rejects command"],"standalone_mcp_connection":False},"task_tools":list(TOOLS),"physical_coordinates":False,"images_to_jev":False,"input_ownership":input_policy(),
      "thresholds":"scoped synthetic holdout profiles plus engineering defaults" if policy else "engineering initial values, uncalibrated",
      "decision_policy":policy.id if policy else None,"policy_model":policy.model if policy else None,
      "policy_profiles":[p.model_dump() for p in policy.profiles] if policy else [],"production_calibrated":False,
      "automatic_background_calibration":False,"routing_policy":describe_routing_policy(),"data_retention_days":7,"semantic_rules":describe(),
      "unsupported":["secure desktop/UAC","unstructured Canvas/video/remote desktop","unknown application planning","generated text","desktop coordinate drag","non-HGLOBAL clipboard handles","official Chrome without active Codex Browser Use session","official Chrome iframe coordinate gestures","official Chrome JS native dialog actions on current host"]}

def initial(token,c):
    return {"status":"running","task_id":token[:32],"completed":[],"remaining":[s.id for s in c.steps],
       "evidence_refs":[],"usage":{},"escalation_reason":None,"resume_token":token}

async def wait_result(directory,wait_seconds,process=None):
    end=time.monotonic()+wait_seconds
    while True:
        result=storage.read(directory/"result.dpapi")
        if result["status"]=="running" and process is not None and process.poll() is not None:
            result.update(status="blocked",escalation_reason="WORKER_EXITED_FINAL_STATE_UNVERIFIED")
            storage.save(directory/"result.dpapi",result)
        if result["status"]!="running" or time.monotonic()>=end:return result
        await asyncio.sleep(0.2)

async def run_task(arguments):
    from .contract_io import load
    c=Contract.model_validate(load(arguments));validate_contract(c)
    if (storage.DATA/"STOP").exists():raise Stop("EMERGENCY_STOP_ACTIVE","blocked")
    token,directory=storage.create(c)
    storage.save(directory/"result.dpapi",initial(token,c))
    # No task text/secrets/commands in argv. Child loads a private DPAPI envelope by opaque ID.
    env={k:v for k,v in os.environ.items() if k.upper() in {"PATH","SYSTEMROOT","SYSTEMDRIVE","WINDIR","PROGRAMFILES","PROGRAMFILES(X86)","PROGRAMW6432","TEMP","TMP","USERPROFILE","APPDATA","LOCALAPPDATA","PYTHONUTF8","TYPESAFE_API_KEY"}}
    env["PYTHONUTF8"]="1"
    process=subprocess.Popen([sys.executable,"-u","-m","gui_delegate.worker",token[:32]],cwd=ROOT,
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    return await wait_result(directory,35,process)

async def resume_task(arguments):
    args=Resume.model_validate(arguments);directory=storage.task_directory(args.resume_token)
    result=storage.read(directory/"result.dpapi")
    if args.input_updates and args.decision_override:raise Stop("ONE_REPAIR_PER_RESUME","blocked")
    if args.continue_task and result.get("escalation_reason") in ("USER_TAKEOVER","USER_CLIPBOARD_CHANGED","CHROME_SESSION_INTERRUPTED") and not args.user_released_control:
        raise Stop("USER_RELEASE_REQUIRED","paused")
    if args.continue_task and result["status"] in ("cancelled","blocked","failed"):
        return {**result,"status":"blocked","escalation_reason":"TERMINATED_TASK_NO_BLIND_REPLAY"}
    if args.input_updates:
        if not args.continue_task or result["status"]!="escalated" or result["escalation_reason"]!="INPUT_TEXT_REQUIRED":raise Stop("INPUT_UPDATE_NOT_ALLOWED","blocked")
        request=storage.read(directory/"request.dpapi");contract=Contract.model_validate(request["contract"])
        for name,value in args.input_updates.items():
            if name not in contract.inputs or not contract.inputs[name].pending:raise Stop("INPUT_UPDATE_NOT_ALLOWED","blocked")
            contract.inputs[name]=contract.inputs[name].model_copy(update={"value":value,"pending":False})
        contract=Contract.model_validate(contract.model_dump());validate_contract(contract)
        request["contract"]=contract.model_dump();storage.save(directory/"request.dpapi",request)
    if args.decision_override:
        allowed={"LOW_CONFIDENCE","AMBIGUOUS_EXACT_MATCH","AMBIGUOUS_SEMANTIC_TARGET","JEV_NO_MATCH","JEV_ASK_ASTRA","JEV_NETWORK_TIMEOUT","JEV_NETWORK_ERROR","JEV_RATE_LIMITED","OVERRIDE_STALE"}
        if not args.continue_task or result["status"]!="escalated" or result["escalation_reason"] not in allowed:raise Stop("DECISION_OVERRIDE_NOT_ALLOWED","blocked")
        checkpoint=storage.read(directory/"checkpoint.dpapi")
        if checkpoint["phase"]=="dispatched":raise Stop("DISPATCHED_ACTION_CANNOT_BE_REPLAYED","blocked")
        context=storage.read(directory/"decision-request.dpapi");override=args.decision_override.model_dump()
        if override["step_id"]!=context["step_id"] or override["observation_fingerprint"]!=context["observation_fingerprint"] or override["control_id"] not in [x["id"] for x in context["candidates"]]:raise Stop("OVERRIDE_TARGET_NOT_ELIGIBLE","blocked")
        storage.save(directory/"override.dpapi",override)
    if args.continue_task and result["status"] not in ("completed","running"):
        if not (directory/"heartbeat").exists() or time.time()-(directory/"heartbeat").stat().st_mtime>3:
            result.update(status="blocked",escalation_reason="WORKER_GONE_NO_BLIND_REPLAY")
            return result
        # Reuses the original contract only; this cannot enlarge scope or grant permissions.
        storage.atomic(directory/"resume",b"1")
        for _ in range(15):
            await asyncio.sleep(0.1)
            if not (directory/"resume").exists():break
    return await wait_result(directory,args.wait_seconds)

async def cancel_task(arguments):
    args=Cancel.model_validate(arguments);directory=storage.task_directory(args.resume_token)
    storage.atomic(directory/"cancel",b"1")
    for _ in range(30):
        result=storage.read(directory/"result.dpapi")
        if result["status"] in ("cancelled","completed","blocked","failed"):break
        await asyncio.sleep(0.1)
    if result['status'] in ('running','paused','escalated','needs_confirmation'):
        heartbeat=directory/'heartbeat'
        if not heartbeat.exists() or time.time()-heartbeat.stat().st_mtime>50:
            result={**result,'status':'blocked','escalation_reason':'WORKER_GONE_FINAL_STATE_UNVERIFIED'}
            storage.save(directory/'result.dpapi',result)
        else:result={**result,"status":"running","escalation_reason":"CANCEL_REQUESTED_RECONCILING_INFLIGHT_ACTION"}
    return result

async def diagnose_task(arguments):
    args=Diagnose.model_validate(arguments)
    if not args.resume_token:return capabilities()
    directory=storage.task_directory(args.resume_token)
    return {"result":storage.read(directory/"result.dpapi"),"checkpoint":storage.read(directory/"checkpoint.dpapi") if (directory/"checkpoint.dpapi").exists() else None,
        "events_path":str(directory/"events.jsonl"),"private_state":"DPAPI encrypted; not returned by tool", "fallback_grant":storage.read(directory/"fallback.dpapi") if (directory/"fallback.dpapi").exists() else None}
