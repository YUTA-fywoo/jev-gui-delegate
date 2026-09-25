"""Local authority checks; page text and model output can never grant permissions."""
import ctypes
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit, unquote
import win32api
import win32con
import win32security
from .schema import Contract

class Stop(Exception):
    def __init__(self, reason, status="escalated"):
        self.reason,self.status=reason,status
        super().__init__(reason)

SECRET=re.compile(r"(?i)(apikey_|sk-[a-z0-9]{12}|bearer\s+[a-z0-9]|(?:password|api[_ -]?key|cookie|验证码|パスワード)\s*[:=]|\b\d{6}\b)")
RISK=re.compile(r"(?i)(pay|purchase|checkout|send|publish|delete|remove|submit|transfer|sign.?in|log.?in|password|security|付款|支付|购买|发送|发布|删除|提交|转账|登录|密码|送信|公開|削除|購入|支払|ログイン)")

def safe_text(value):
    if SECRET.search(value) or len(value)>320: raise Stop("SENSITIVE_OR_UNBOUNDED_OBSERVATION")
    return value

def protect_directory(path):
    path=Path(path);path.mkdir(parents=True,exist_ok=True)
    token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
    sid=win32security.GetTokenInformation(token,win32security.TokenUser)[0]
    token.Close()
    acl=win32security.ACL()
    acl.AddAccessAllowedAceEx(win32security.ACL_REVISION,3,win32con.GENERIC_ALL,sid)
    acl.AddAccessAllowedAceEx(win32security.ACL_REVISION,3,win32con.GENERIC_ALL,
        win32security.CreateWellKnownSid(win32security.WinLocalSystemSid,None))
    win32security.SetNamedSecurityInfo(str(path),win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION|win32security.PROTECTED_DACL_SECURITY_INFORMATION,None,None,acl,None)

def within(path, roots, must_exist=False):
    p=Path(path)
    if not p.is_absolute() or str(p).startswith("\\\\") or ":" in str(p)[2:]: raise Stop("PATH_DENIED","blocked")
    resolved=p.resolve(strict=must_exist)
    # Reject junction/symlink traversal even when it returns inside a scope.
    for part in [p]+list(p.parents):
        if part.exists() and part.is_symlink(): raise Stop("REPARSE_PATH_DENIED","blocked")
        if part.exists() and getattr(part.stat(follow_symlinks=False),"st_file_attributes",0)&0x400: raise Stop("REPARSE_PATH_DENIED","blocked")
    if not any(resolved.is_relative_to(Path(r).resolve()) for r in roots): raise Stop("PATH_DENIED","blocked")
    return resolved

def origin(url):
    u=urlsplit(url)
    if u.username or u.password: raise Stop("URL_CREDENTIALS_DENIED","blocked")
    if u.scheme not in ("https","http"): raise Stop("URL_SCHEME_DENIED","blocked")
    return u.scheme+"://"+u.netloc.lower()

def check_url(url, contract):
    u=urlsplit(url)
    if u.scheme=="file":
        if u.netloc: raise Stop("REMOTE_FILE_DENIED","blocked")
        p=unquote(u.path).lstrip("/")
        return str(within(p,contract.scope.read_roots,True))
    if origin(url) not in contract.scope.origins: raise Stop("ORIGIN_DENIED","blocked")
    return url

def validate_contract(c:Contract):
    for p in c.scope.read_roots+c.scope.write_roots+c.scope.programs:
        if not Path(p).is_absolute(): raise Stop("ABSOLUTE_SCOPE_REQUIRED","blocked")
    if c.target.driver=="browser": check_url(c.target.url,c)
    if c.target.driver=="windows":
        if os.path.normcase(c.target.executable) not in {os.path.normcase(p) for p in c.scope.programs}:
            raise Stop("PROGRAM_DENIED","blocked")
    if any(v.sensitive for v in c.inputs.values()): raise Stop("SENSITIVE_INPUT_REQUIRES_USER","escalated")
    for value in c.inputs.values():
        if SECRET.search(value.value): raise Stop("SENSITIVE_INPUT_REQUIRES_USER")
        if value.kind=="path": within(value.value,c.scope.read_roots+c.scope.write_roots)
    for text in c.jev_label_allowlist: safe_text(text)
    for step in c.steps:
        if step.op in ('navigate','new_tab'):
            value=c.inputs[step.input_ref]
            if value.pending or value.captured:raise Stop('EXPLICIT_NAVIGATION_URL_REQUIRED','blocked')
            check_url(value.value,c)
        if step.op in ('screenshot','export','logs','assets','clipboard_read'):
            value=c.inputs[step.input_ref]
            if value.kind!='path':raise Stop('PATH_REFERENCE_REQUIRED','blocked')
            within(value.value,c.scope.write_roots)
        options=step.browser_options
        if step.op=='viewport_set' and (not options or options.viewport_width is None or options.viewport_height is None):raise Stop('VIEWPORT_DIMENSIONS_REQUIRED','blocked')
        if options and options.upload_refs:
            for ref in options.upload_refs:
                item=c.inputs[ref]
                if item.kind!='path' or item.pending or item.captured:raise Stop('EXPLICIT_UPLOAD_FILES_REQUIRED','blocked')
                within(item.value,c.scope.read_roots,True)
        if options and options.download_directory:
            within(options.download_directory,c.scope.read_roots,True)
        if options and options.expected_download_name:
            name=options.expected_download_name
            if name in ('.','..') or any(x in name for x in ('/',chr(92),':','*','?','\x00')):raise Stop('DOWNLOAD_NAME_DENIED','blocked')
    for target in c.targets.values():
        child=c.model_copy(update={'target':target,'targets':{}})
        if target.driver=='windows' and not all((target.hwnd,target.process_id,target.executable,target.window_title)):raise Stop('WINDOW_IDENTITY_REQUIRED','blocked')
        validate_contract(child)

def authorize(step,control,contract,location):
    if step.op not in contract.scope.actions: raise Stop("ACTION_DENIED","blocked")
    if control and control.password: raise Stop("LOGIN_REQUIRES_USER")
    if control and control.role.lower() in ("canvas","video","image") and step.op not in ("read","wait"):
        raise Stop("NO_RELIABLE_ACTION_SEMANTICS")
    if control and control.role.lower() in ("button","link") and not control.name and not control.automation_id:
        raise Stop("UNLABELED_CONTROL_REQUIRES_ASTRA")
    if control and (not control.enabled or not control.visible): raise Stop("CONTROL_NOT_ACTIONABLE")
    if step.op in ("read","wait","scroll","switch_tab"): return
    risk=step.effect not in ("none","local") or step.op in ('upload','dialog_accept') or (step.op=='close_tab' and step.browser_options and step.browser_options.allow_close_existing) or (step.op=='key' and contract.inputs[step.input_ref].value in ('Enter','Space')) or (control and RISK.search(control.name))
    if control and control.attributes.get("href") and step.op in ("click","context_click"):
        check_url(control.attributes["href"],contract)
    if control and control.attributes.get("submit")=="true": risk=True
    if risk:
        name=control.name if control else ""
        matches=[a for a in contract.authorizations if a.step_id==step.id and a.effect==step.effect and
            a.target_name==name and a.destination==location]
        if len(matches)!=1: raise Stop("EXPLICIT_TARGET_AUTHORIZATION_REQUIRED","needs_confirmation")
    if step.op in ("upload","download"):
        v=contract.inputs[step.input_ref]
        if v.kind!="path": raise Stop("PATH_REFERENCE_REQUIRED","blocked")
        p=within(v.value,contract.scope.read_roots if step.op=="upload" else contract.scope.write_roots,step.op=="upload")
        if step.op=="download" and p.exists(): raise Stop("OVERWRITE_REQUIRES_USER","needs_confirmation")

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def last_input_tick():
    class LII(ctypes.Structure):
        _fields_=[("cbSize",ctypes.c_uint),("dwTime",ctypes.c_uint)]
    info=LII();info.cbSize=ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)): raise Stop("INPUT_MONITOR_UNAVAILABLE","blocked")
    return info.dwTime
