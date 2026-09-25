"""Narrow read-only probes of separately opened Explorer/Settings test windows."""
import asyncio,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jev_client import ROOT
from gui_delegate.schema import Contract
from gui_delegate.drivers import Windows
from gui_delegate.service import run_task,cancel_task

def image_path(pid):
    import ctypes,win32api,win32con
    h=win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION,False,pid)
    try:
        size=ctypes.c_ulong(32768);buf=ctypes.create_unicode_buffer(size.value)
        if not ctypes.windll.kernel32.QueryFullProcessImageNameW(int(h),0,buf,ctypes.byref(size)):raise RuntimeError('process query failed')
        return buf.value
    finally:h.Close()

def contract(hwnd):
    import win32gui,win32process
    _,pid=win32process.GetWindowThreadProcessId(hwnd);exe=image_path(pid)
    return {'goal':'Read a safe control in an owned application test window','target':{'driver':'windows','hwnd':hwnd,'process_id':pid,'executable':exe,'window_title':win32gui.GetWindowText(hwnd)},
       'scope':{'programs':[exe],'read_roots':[str(ROOT/'gui_delegate/fixtures')],'actions':['read']},
       'steps':[{'id':'read','intent':'Read known safe structure','op':'read','target':{'role':'Button','name':'placeholder'},'after':[{'kind':'exists','target':{'role':'Button','name':'placeholder'}}]}],
       'success':[{'kind':'exists','target':{'role':'Button','name':'placeholder'}}],'budget':{'seconds':25}}

def run_observation(hwnd,preferred):
    c=contract(hwnd);d=Windows(Contract.model_validate(c));d.open();obs=d.observe()
    candidates=[x for x in obs.controls if x.visible and x.enabled and x.name in preferred]
    for candidate in candidates:
        query={'role':candidate.role,'name':candidate.name,'automation_id':candidate.automation_id or None}
        if sum(x.role==candidate.role and x.name==candidate.name and x.automation_id==candidate.automation_id for x in obs.controls)==1:
            c['steps'][0]['target']=query;c['steps'][0]['after']=[{'kind':'exists','target':query}];c['success']=c['steps'][0]['after']
            result=asyncio.run(run_task(c))
            if result['status']!='completed':asyncio.run(cancel_task({'resume_token':result['resume_token']}))
            return {'structured_controls':len(obs.controls),'result':result,'jev_requests':0}
    return {'status':'BLOCKED','reason':'SAFE_UNIQUE_CONTROL_NOT_FOUND','structured_controls':len(obs.controls),'jev_requests':0}

def main():
    import pythoncom,win32com.client,win32gui
    pythoncom.CoInitialize();report={};folder=str(ROOT/'gui_delegate/fixtures')
    shell=win32com.client.Dispatch('Shell.Application')
    def windows():
        result={}
        for w in shell.Windows():
            try:result[int(w.HWND)]=str(w.Document.Folder.Self.Path)
            except Exception:pass
        return result
    before=windows();hwnd=None
    try:
        subprocess.Popen([str(Path(os.environ['WINDIR'])/'explorer.exe'),'/n,',folder],creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.time()+15
        while time.time()<deadline:
            found=[h for h,p in windows().items() if h not in before and os.path.normcase(p)==os.path.normcase(folder)]
            if len(found)==1:hwnd=found[0];break
            time.sleep(.2)
        report['explorer']=run_observation(hwnd,['sample.txt','sample','搜索框','新建','返回']) if hwnd else {'status':'BLOCKED','reason':'NO_DISTINCT_TEST_EXPLORER_WINDOW'}
    except Exception as exc:report['explorer']={'status':'BLOCKED','reason':type(exc).__name__}
    finally:
        if hwnd and hwnd not in before and win32gui.IsWindow(hwnd):win32gui.PostMessage(hwnd,0x10,0,0)
    from pywinauto import Desktop
    existing=[w.handle for w in Desktop(backend='uia').windows() if w.window_text() in ('设置','Settings')]
    hwnd=None
    try:
        if existing:report['settings']={'status':'SKIPPED','reason':'Existing user Settings window preserved'}
        else:
            os.startfile('ms-settings:about');deadline=time.time()+15
            while time.time()<deadline:
                found=[w.handle for w in Desktop(backend='uia').windows() if w.window_text() in ('设置','Settings')]
                if len(found)==1:hwnd=found[0];break
                time.sleep(.25)
            report['settings']=run_observation(hwnd,['主页','系统','隐私和安全性','Home','System']) if hwnd else {'status':'BLOCKED','reason':'SETTINGS_WINDOW_UNAVAILABLE'}
    except Exception as exc:report['settings']={'status':'BLOCKED','reason':type(exc).__name__}
    finally:
        if hwnd and hwnd not in existing and win32gui.IsWindow(hwnd):win32gui.PostMessage(hwnd,0x10,0,0)
    report['electron']={'status':'SKIPPED','reason':'No isolated Electron test application provisioned; current Codex production window was not inspected.'}
    report['physical_input']={'monitor_count':__import__('win32api').GetSystemMetrics(80),'coordinate_actions':'unsupported; semantic patterns only','ime':'SetValue/DOM fill bypasses IME; physical composition not tested','clipboard':'not touched by executor; copy/paste adapter unsupported'}
    (ROOT/'gui_delegate/reports/windows-apps.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
