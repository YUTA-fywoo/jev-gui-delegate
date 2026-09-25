"""Task transport entry point, launched only by the in-session Chrome adapter."""
import asyncio,json,sys
from . import storage,service
from .schema import Contract
from .security import Stop,validate_contract
from .chrome_session import StdioBrowserSession
from .worker import work

def capability_escalation(c,reason):
    """Record a verified host limitation, never execute a GUI action at preflight."""
    import time
    from .fallback_policy import issue,routing
    token,directory=storage.create(c)
    value={**service.initial(token,c),'status':'escalated','usage':{'actions':0,'jev_requests':0},
           'escalation_reason':reason,'verification':[],
           'evidence_refs':[str(directory/'events.jsonl')], 'routing':routing({},reason)}
    storage.save(directory/'result.dpapi',value)
    storage.event(directory,'host_capability_preflight',reason=reason,actions=0)
    issue(directory,c,reason,time.time()+c.budget.seconds)
    return {'valid':False,**value}

def main():
    line=sys.stdin.buffer.readline(1_000_001)
    if len(line)>1_000_000:raise ValueError('request too large')
    message=json.loads(line)
    if message.get('action')=='control':
        operation=message.get('operation');args=message.get('arguments',{})
        if operation=='record_chrome_cleanup':
            directory=storage.task_directory(args['resume_token'])
            request=storage.read(directory/'request.dpapi')
            if request['contract']['target']['connection']!='official_chrome':raise ValueError('wrong driver')
            stats=args['stats'];allowed={'tabs_created','tabs_closed_during_run','tabs_closed_at_end','tabs_closed_explicitly','tabs_peak_owned','tabs_retained','tabs_cleanup_deferred'}
            if set(stats)!=allowed or any(type(v) is not int or not 0<=v<=1000 for v in stats.values()):raise ValueError('invalid counters')
            result=storage.read(directory/'result.dpapi');result['usage'].update(stats)
            storage.save(directory/'result.dpapi',result);storage.event(directory,'browser_tabs_final',**stats)
            print(json.dumps({'recorded':True}));return
        if operation=='validate_chrome_contract':
            from .chrome_policy import require_enabled
            require_enabled()
            if not service.enabled():raise Stop('GUI_DELEGATE_DISABLED','blocked')
            if (storage.DATA/'STOP').exists():raise Stop('EMERGENCY_STOP_ACTIVE','blocked')
            c=Contract.model_validate(args['contract']);validate_contract(c)
            if c.target.connection!='official_chrome' or any(t.connection!='official_chrome' for t in c.targets.values()):raise Stop('CHROME_MIXED_DESKTOP_REQUIRES_SEPARATE_TASK')
            from .chrome_session import OPS
            if any(s.op not in OPS for s in c.steps):raise Stop('CHROME_UNSUPPORTED_ACTION')
            if any(s.op in ('dialog_accept','dialog_dismiss') for s in c.steps):
                print(json.dumps(capability_escalation(c,'CHROME_JS_DIALOG_HOST_BLOCKED')));return
            print(json.dumps({'valid':True}));return
        if operation not in ('resume_task','cancel_task','diagnose_task'):raise ValueError('unsupported control')
        output=asyncio.run(getattr(service,operation)(args))
        print(json.dumps(output,ensure_ascii=True));return
    if set(message)!={'action','contract'} or message['action']!='run':raise ValueError('invalid request')
    c=Contract.model_validate(message['contract']);validate_contract(c)
    from .chrome_policy import require_enabled
    require_enabled()
    if not service.enabled():raise Stop('GUI_DELEGATE_DISABLED','blocked')
    if c.target.connection!='official_chrome' or any(t.connection!='official_chrome' for t in c.targets.values()):raise Stop('CHROME_IDENTITY_MISMATCH','blocked')
    if (storage.DATA/'STOP').exists():raise Stop('EMERGENCY_STOP_ACTIVE','blocked')
    token,directory=storage.create(c)
    storage.save(directory/'result.dpapi',service.initial(token,c))
    session=StdioBrowserSession()
    session.emit({'type':'started','resume_token':token})
    work(token[:32],browser_session=session,status_sink=lambda data:session.emit({'type':'result','value':data}))
    session.closed.wait(1)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Errors carry no raw input, exception message, path, page text or credential.
        reason=exc.reason if isinstance(exc,Stop) else 'CHROME_REQUEST_INVALID'
        print(json.dumps({'type':'fatal','reason':reason,'status':exc.status if isinstance(exc,Stop) else 'blocked'}),flush=True)
        sys.exit(1)
