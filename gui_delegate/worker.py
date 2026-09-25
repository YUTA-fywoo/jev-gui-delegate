import ctypes
import os
import re
import sys
import time
import win32api
import win32event
import winerror
from . import storage
from .schema import Contract,Checkpoint,Result,NON_DOM_OPS
from .security import Stop,validate_contract,digest,SECRET
from .input_guard import InputGuard
from .drivers import create_driver
from .controller import Controller,verified,predicate,matches
from .fallback_policy import issue as issue_fallback,routing

def work(task_id,browser_session=None,status_sink=None):
    if not re.fullmatch(r"[a-f0-9]{32}",task_id):return
    directory=storage.DATA/task_id
    request=storage.read(directory/"request.dpapi");token=request["token"]
    c=Contract.model_validate(request["contract"]);start=time.monotonic();deadline=request["created_at"]+c.budget.seconds
    checkpoint=Checkpoint(task_id=task_id,contract_hash=digest(c.model_dump()),next_step=0,completed=[],phase="idle")
    driver=None;controller=None;mutex=None;locked=False;input_guard=None
    heartbeat=directory/"heartbeat";last_observation=None;success_observations={}
    # A Windows Job Object owns only this worker and any children it creates.
    # Attached existing applications are not members and can never be terminated here.
    import win32job,threading
    job=win32job.CreateJobObject(None,"")
    job_info=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation)
    job_info["BasicLimitInformation"]["LimitFlags"]=win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,job_info)
    win32job.AssignProcessToJobObject(job,win32api.GetCurrentProcess())
    finished=threading.Event()
    def result(status,reason=None):
        usage=dict(controller.usage) if controller else {}
        if usage.get("escalations",0):usage["astra_fallbacks"]="unavailable"
        usage["elapsed_ms"]=round((time.monotonic()-start)*1000)
        checks=[]
        if status=="completed" and last_observation:
            for index,p in enumerate(c.success):
                check_obs=success_observations.get(p.surface,last_observation)
                item={"condition":index,"kind":p.kind,"surface":p.surface,"passed":predicate(p,check_obs,c,controller.artifacts)}
                if p.input_ref:item["matched_input_ref"]=p.input_ref
                elif p.kind in ("text","checked") and p.target:
                    found=[control for control in check_obs.controls if matches(control,p.target)]
                    if len(found)==1:
                        value=found[0].checked if p.kind=="checked" else found[0].attributes.get("text")
                        if isinstance(value,bool) or (isinstance(value,str) and len(value)<=60 and not SECRET.search(value)):
                            item["observed"]=value
                checks.append(item)
        context=controller.decision_context if controller and status=="escalated" else None
        if context and (checkpoint.next_step>=len(c.steps) or context.get('step_id')!=c.steps[checkpoint.next_step].id):context=None
        output=Result(status=status,task_id=task_id,completed=list(checkpoint.completed),remaining=[s.id for s in c.steps[checkpoint.next_step:]],
            evidence_refs=[str(directory/"events.jsonl")],usage=usage,escalation_reason=reason,resume_token=token,verification=checks,
            escalation_context=context,
            routing=routing(usage,reason))
        storage.save(directory/"result.dpapi",output.model_dump())
        if status_sink:status_sink(output.model_dump())
        return output
    def fallback(reason):
        return issue_fallback(directory,c,reason,deadline)
    def record(kind,**data):
        nonlocal last_observation
        if kind=="observation":
            obs=data["observation"];last_observation=obs
            storage.save(directory/f"observation-{obs.sequence%8}.dpapi",obs.model_dump())
            storage.event(directory,kind,sequence=obs.sequence,fingerprint=obs.fingerprint,controls=len(obs.controls))
        elif kind=="checkpoint":storage.save(directory/"checkpoint.dpapi",data["checkpoint"].model_dump())
        elif kind=="decision_request":storage.save(directory/"decision-request.dpapi",data["context"])
        elif kind=='artifacts':storage.save(directory/'artifacts.dpapi',data['values'])
        else:storage.event(directory,kind,**data)
        heartbeat.touch()
    def stop_check():
        heartbeat.touch()
        if (storage.DATA/"STOP").exists() or (directory/"cancel").exists():raise Stop("CANCELLED","cancelled")
        if (ctypes.windll.user32.GetAsyncKeyState(0x11)&0x8000 and ctypes.windll.user32.GetAsyncKeyState(0x12)&0x8000 and ctypes.windll.user32.GetAsyncKeyState(0x7B)&0x8000):
            storage.atomic(storage.DATA/"STOP",b"1");raise Stop("EMERGENCY_STOP","cancelled")
        if time.time()>=deadline:raise Stop("TASK_DEADLINE","blocked")
        if browser_session and checkpoint.next_step<len(c.steps):browser_session.check_segment()
        if input_guard:input_guard.check()
    def watchdog():
        while not finished.wait(0.25):
            if all(ctypes.windll.user32.GetAsyncKeyState(k)&0x8000 for k in (0x11,0x12,0x7B)):
                storage.atomic(storage.DATA/"STOP",b"hotkey")
            stalled=heartbeat.exists() and time.time()-heartbeat.stat().st_mtime>50
            cancel_stalled=((storage.DATA/"STOP").exists() or (directory/"cancel").exists()) and heartbeat.exists() and time.time()-heartbeat.stat().st_mtime>5
            if time.time()>deadline+2 or stalled or cancel_stalled:
                # Do not invent a final UI result when a driver itself is hung.
                try:
                    if cancel_stalled and checkpoint.phase!="dispatched":result("cancelled","CANCELLED")
                    else:result("blocked","INFLIGHT_FINAL_STATE_UNVERIFIED" if checkpoint.phase=="dispatched" else "WORKER_DEADLINE")
                finally:os._exit(70)
    threading.Thread(target=watchdog,daemon=True).start()
    try:
        validate_contract(c)
        mutex=win32event.CreateMutex(None,False,"Local\\CodexJevGuiDesktop")
        if win32event.WaitForSingleObject(mutex,0) not in (win32event.WAIT_OBJECT_0,win32event.WAIT_ABANDONED):raise Stop("DESKTOP_BUSY","blocked")
        locked=True
        input_guard=InputGuard(c);input_guard.start()
        record('input_guard',mode=input_guard.mode)
        driver=create_driver(c,input_guard=input_guard,browser_session=browser_session);driver.open()
        controller=Controller(c,driver,stop_check,record)
        record("checkpoint",checkpoint=checkpoint)
        while checkpoint.next_step<len(c.steps):
            try:
                stop_check();step=c.steps[checkpoint.next_step]
                if checkpoint.phase=="dispatched":
                    # A timed-out/failed action is only reconciled. Never automatically replay it.
                    obs=controller.observe()
                    if not verified(step,obs,c,checkpoint.pending_control_id,controller.artifacts) or (step.op not in NON_DOM_OPS and obs.fingerprint==checkpoint.before_fingerprint):raise Stop("UNCERTAIN_ACTION_REQUIRES_RECONCILIATION")
                else:controller.perform(step,checkpoint)
                checkpoint.completed.append(step.id);checkpoint.next_step+=1;checkpoint.phase="idle";checkpoint.pending_step=None
                record("checkpoint",checkpoint=checkpoint)
                if hasattr(driver,'checkpoint'):
                    stop_check()
                    tab_stats=driver.checkpoint(checkpoint.completed)
                    controller.usage.update(tab_stats);record('browser_tabs',**tab_stats)
                result("running")
            except Stop as exc:
                checkpoint.reason=exc.reason;record("checkpoint",checkpoint=checkpoint)
                controller.usage["escalations"]+=int(exc.status=="escalated")
                # Decision repair is not permission for a direct GUI takeover.
                fallback(exc.reason)
                result(exc.status,exc.reason)
                if exc.status in ("blocked","failed","cancelled"):return
                # Keep owned browser/windows handles alive for local repair and resume, bounded by original deadline.
                while time.time()<deadline:
                    heartbeat.touch()
                    if (directory/"cancel").exists() or (storage.DATA/"STOP").exists():result("cancelled","CANCELLED");return
                    if (directory/"resume").exists():
                        (directory/"resume").unlink(missing_ok=True)
                        if (storage.DATA/"STOP").exists():result("cancelled","EMERGENCY_STOP_ACTIVE");continue
                        new=Contract.model_validate(storage.read(directory/"request.dpapi")["contract"])
                        old_scope=c.model_dump();new_scope=new.model_dump();old_scope.pop("inputs");new_scope.pop("inputs")
                        if old_scope!=new_scope:raise Stop("RESUME_SCOPE_CHANGED","blocked")
                        for name,old_input in c.inputs.items():
                            if not old_input.pending and old_input!=new.inputs[name]:raise Stop("RESUME_EXISTING_INPUT_CHANGED","blocked")
                        validate_contract(new);c=new;controller.contract=c;controller.cache.clear();checkpoint.contract_hash=digest(c.model_dump())
                        for name in ('fallback.dpapi','fallback-binding.dpapi'):(directory/name).unlink(missing_ok=True)
                        if (directory/"override.dpapi").exists():
                            controller.override=storage.read(directory/"override.dpapi");(directory/"override.dpapi").unlink()
                        (directory/"cancel").unlink(missing_ok=True)
                        if checkpoint.reason in ('USER_TAKEOVER','USER_CLIPBOARD_CHANGED'):input_guard.release()
                        if browser_session:browser_session.reset_segment()
                        result("running");break
                    time.sleep(0.2)
                else:result("blocked","RESUME_WINDOW_EXPIRED");return
        for surface in dict.fromkeys(p.surface for p in c.success):
            if hasattr(driver,'activate'):driver.activate(surface)
            success_observations[surface]=controller.observe()
        if not all(predicate(p,success_observations[p.surface],c,controller.artifacts) for p in c.success):raise Stop("FINAL_SUCCESS_NOT_PROVEN")
        result("completed")
    except Stop as exc:
        if exc.status=="escalated":fallback(exc.reason)
        result(exc.status,exc.reason)
    except Exception as exc:
        import traceback
        storage.event(directory,"runtime_error",exception_type=type(exc).__name__,frames=[{"file":os.path.basename(f.filename),"line":f.lineno,"function":f.name} for f in traceback.extract_tb(exc.__traceback__)])
        result("failed","LOCAL_RUNTIME_FAILURE")
    finally:
        if driver:
            try:driver.close()
            except Exception:pass
        if input_guard:input_guard.close()
        if locked:win32event.ReleaseMutex(mutex)
        if mutex:win32api.CloseHandle(mutex)
        heartbeat.unlink(missing_ok=True)
        finished.set()
        # Keep job handle alive until process exit; closing it here would kill this process early.

if __name__=="__main__":work(sys.argv[1])
