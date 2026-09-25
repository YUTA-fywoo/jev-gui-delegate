"""Same local Controller, official Chrome API executed in the bound Codex REPL.

The worker has no access to a private browser endpoint or to Codex credentials.
It exchanges a small fixed protocol over anonymous child-process stdio. No HTTP
listener, arbitrary code, selectors, screenshots, cookies, or browser profiles.
"""
import json
import queue
import sys
import threading
import time
from .security import Stop,check_url,within
from .schema import Control
from .drivers import observation

OPS={'read','wait','click','fill','select','check','uncheck','context_click','key','copy','paste','double_click','hover','scroll','range','drag','upload','download','switch_tab','close_tab','navigate','new_tab','back','forward','reload','screenshot','export','logs','assets','dialog_accept','dialog_dismiss','clipboard_write','clipboard_read','mark_deliverable','mark_handoff','viewport_set','viewport_reset'}
SAFE_ERRORS={'USER_TAKEOVER','CHROME_SESSION_INTERRUPTED','CHROME_PAGE_CHANGED','CHROME_TAB_CLOSED',
 'CHROME_AMBIGUOUS_CONTROL','CHROME_CONTROL_STALE','CHROME_UNSUPPORTED_ACTION','CHROME_PASSWORD_CONTROL',
 'CHROME_DIALOG_REQUIRES_REVIEW','CHROME_ORIGIN_DENIED','CHROME_FRAME_UNSUPPORTED','CHROME_STATE_TOO_LARGE',
 'CHROME_ELEMENT_NOT_ACTIONABLE','CHROME_SESSION_NOT_RUNNING','CHROME_INPUT_NOT_ALLOWED','CHROME_READONLY_SCOPE_UNAVAILABLE',
 'CHROME_IDENTITY_MISMATCH','CHROME_SEGMENT_COMPLETE','CHROME_DRIVER_ERROR'}
SAFE_ERRORS.update({'CHROME_BACKEND_CAPABILITY_UNAVAILABLE','CHROME_ASSET_LIMIT','CHROME_SCREENSHOT_FORMAT_UNKNOWN','CHROME_SCREENSHOT_REQUIRES_PNG_PATH','CHROME_SCREENSHOT_REQUIRES_JPEG_PATH','CHROME_UPLOAD_MULTIPLE_NOT_SUPPORTED','CHROME_JS_DIALOG_HOST_BLOCKED','CHROME_VIEWPORT_UNVERIFIED','CHROME_FRAME_DEPTH_LIMIT','CHROME_FRAME_IDENTITY_UNAVAILABLE','CHROME_FRAME_CHANGED','CHROME_FRAME_COORDINATES_REQUIRE_ASTRA','CHROME_GEOMETRY_UNSAFE','CHROME_RANGE_DENIED','CHROME_RANGE_UNVERIFIED','CHROME_PATH_DENIED','CHROME_FILE_MISSING','CHROME_OUTPUT_EXISTS','CHROME_FILE_VERIFICATION_FAILED','CHROME_ARTIFACT_UNAVAILABLE','CHROME_UPLOAD_FILE_ACCESS_REQUIRED','CHROME_DOWNLOAD_DESTINATION_REQUIRED','CHROME_DOWNLOAD_NAME_CHANGED','CHROME_BROWSER_BINDING_REQUIRED','CHROME_NAVIGATION_UNVERIFIED','CHROME_TAB_NOT_UNIQUE','CHROME_LAST_TAB_CLOSE_REQUIRES_ASTRA','CHROME_EXISTING_TAB_CLOSE_REQUIRES_CONFIRMATION','CHROME_HISTORY_OUTSIDE_TASK','CHROME_CLIPBOARD_UNVERIFIED','CHROME_DIALOG_NOT_PRESENT','CHROME_DIALOG_ACTION_DENIED','CHROME_DIALOG_UNVERIFIED','CHROME_SURFACE_DENIED'})

SAFE_ERRORS.update({'CHROME_TASK_TAB_LIMIT','CHROME_CHECKPOINT_INVALID'})

class StdioBrowserSession:
    def __init__(self):
        self.queue=queue.Queue();self.serial=0;self.started=time.monotonic();self.closed=threading.Event()
        threading.Thread(target=self._read,daemon=True).start()
    def _read(self):
        try:
            while True:
                line=sys.stdin.buffer.readline(2_000_001)
                if not line or len(line)>2_000_000:break
                self.queue.put(json.loads(line))
        except Exception:pass
        self.queue.put(None)
        self.closed.set()
    def emit(self,value):
        sys.stdout.write(json.dumps(value,ensure_ascii=True,separators=(',',':'))+'\n');sys.stdout.flush()
    def exchange(self,method,payload):
        self.serial+=1;ident=self.serial
        self.emit({'type':'browser_request','id':ident,'method':method,'payload':payload})
        try:response=self.queue.get(timeout=18)
        except queue.Empty:
            self.closed.set()
            raise Stop('CHROME_SESSION_TIMEOUT','blocked') from None
        if response is None:raise Stop('CHROME_SESSION_DISCONNECTED','blocked')
        if set(response)-{'id','ok','value','error'} or response.get('id')!=ident or type(response.get('ok')) is not bool:
            raise Stop('CHROME_PROTOCOL_INVALID','blocked')
        if not response['ok']:
            reason=response.get('error')
            if reason not in SAFE_ERRORS:reason='CHROME_DRIVER_ERROR'
            status='paused' if reason in ('USER_TAKEOVER','CHROME_SESSION_INTERRUPTED') else 'escalated'
            raise Stop(reason,status)
        return response.get('value')
    def check_segment(self):
        if time.monotonic()-self.started>35:raise Stop('CHROME_SEGMENT_COMPLETE','paused')
    def reset_segment(self):self.started=time.monotonic()

class ChromeSessionDriver:
    supported_ops=OPS
    def __init__(self,contract,session):
        self.contract=contract;self.session=session;self.seq=0;self.controls={};self.current='main'
    def open(self):
        if any(s.op not in self.supported_ops for s in self.contract.steps):raise Stop('CHROME_UNSUPPORTED_ACTION')
        bound=self.session.exchange('bind',{'tab_id':self.contract.target.tab_id,'url':self.contract.target.url,
                                      'origins':self.contract.scope.origins,'operations':sorted(self.contract.scope.actions)})
        self.lifecycle_checkpoints=isinstance(bound,dict) and bound.get('lifecycle_checkpoints') is True
    def observe(self):
        data=self.session.exchange('observe',{})
        if not isinstance(data,dict) or set(data)-{'url','controls','tab_count'} or not {'url','controls'}<=set(data) or len(data['controls'])>600:
            raise Stop('CHROME_PROTOCOL_INVALID','blocked')
        check_url(data['url'],self.contract)
        controls=[Control.model_validate(c) for c in data['controls']]
        if len({c.id for c in controls})!=len(controls):raise Stop('CHROME_PROTOCOL_INVALID','blocked')
        self.controls={c.id:c for c in controls};self.seq+=1
        return observation(self.seq,data['url'],controls,data.get('tab_count',1)).model_copy(update={'surface':self.current})
    def activate(self,name):
        if name not in {'main',*self.contract.targets}:raise Stop('CHROME_SURFACE_DENIED','blocked')
        if name!=self.current:self.session.exchange('activate',{'surface':name});self.current=name
    def act(self,action,step,value):
        if step.op in ('read','wait','copy'):return
        if step.op not in self.supported_ops:raise Stop('CHROME_UNSUPPORTED_ACTION')
        from .schema import PAGE_OPS
        if step.op not in PAGE_OPS and action.control_id not in self.controls:raise Stop('CHROME_CONTROL_STALE')
        options=step.browser_options.model_dump() if step.browser_options else {}
        if step.op=='upload':options['upload_files']=[str(within(self.contract.inputs[ref].value,self.contract.scope.read_roots,True)) for ref in options.pop('upload_refs',[])]
        source=None
        if step.op=='download':
            from pathlib import Path
            directory=options.get('download_directory');name=options.get('expected_download_name')
            if not directory or not name:raise Stop('CHROME_DOWNLOAD_DESTINATION_REQUIRED')
            source=within(str(Path(directory)/name),self.contract.scope.read_roots)
            if source.exists():raise Stop('DOWNLOAD_NAME_ALREADY_EXISTS','blocked')
            output=within(value,self.contract.scope.write_roots)
            if output.exists():raise Stop('OVERWRITE_REQUIRES_USER','needs_confirmation')
        self.session.exchange('act',{'step_id':step.id,'control_id':action.control_id,'destination_control_id':action.destination_control_id,'operation':step.op,'value':value,'options':options})
        if source is not None:
            import shutil
            end=time.monotonic()+8;last_size=None;stable=0
            while time.monotonic()<end:
                if source.is_file() and not source.with_suffix(source.suffix+'.crdownload').exists():
                    size=source.stat().st_size;stable=stable+1 if size==last_size else 0;last_size=size
                    if stable>=2 and size>0:break
                time.sleep(.2)
            else:raise Stop('CHROME_DOWNLOAD_COMPLETION_UNVERIFIED')
            with output.open('xb') as dst,source.open('rb') as src:shutil.copyfileobj(src,dst)
            import hashlib
            if hashlib.sha256(output.read_bytes()).digest()!=hashlib.sha256(source.read_bytes()).digest():raise Stop('CHROME_DOWNLOAD_COPY_UNVERIFIED')
    def checkpoint(self,completed):
        return self.session.exchange('checkpoint',{'completed':completed}) if getattr(self,'lifecycle_checkpoints',False) else {}
    def close(self):
        # The in-session JS adapter owns verified resource cleanup, never this process.
        pass
