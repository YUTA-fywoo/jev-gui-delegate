import asyncio,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jev_client import ROOT
from gui_delegate.service import run_task,resume_task,cancel_task
from gui_delegate.security import Stop

async def main():
    import win32gui
    p=subprocess.Popen([sys.executable,str(ROOT/'gui_delegate/fixtures/native.py'),'--simulate-user-input'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    pid,hwnd=map(int,p.stdout.readline().split())
    try:
        condition={'kind':'exists','target':{'role':'Edit','automation_id':'101'}}
        c={'goal':'Observe the owned fixture and pause when an input event occurs','target':{'driver':'windows','hwnd':hwnd,'process_id':pid,'executable':sys._base_executable,'window_title':'Jev Delegate Native Fixture'},
           'scope':{'programs':[sys._base_executable],'actions':['read']},
           'steps':[{'id':'read_'+str(i),'op':'read','intent':'Observe the owned fixture','target':condition['target'],'after':[condition]} for i in range(25)],
           'success':[condition],'budget':{'seconds':20,'steps':30}}
        r=await run_task(c)
        if r['status']!='paused' or r['escalation_reason']!='USER_TAKEOVER':
            await cancel_task({'resume_token':r['resume_token']})
            if win32gui.IsWindow(hwnd):win32gui.PostMessage(hwnd,0x10,0,0)
            p.wait(timeout=5);messages=p.stdout.read().strip()
            report={'status':'BLOCKED' if 'INPUT_INJECTION_BLOCKED' in messages else 'FAIL','reason':messages or 'No injected input was confirmed','result_status':r['status']}
            (ROOT/'gui_delegate/reports/takeover.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report));return
        try:await resume_task({'resume_token':r['resume_token'],'continue_task':True});raise AssertionError('automatic reclaim allowed')
        except Stop as exc:assert exc.reason=='USER_RELEASE_REQUIRED'
        cancelled=await cancel_task({'resume_token':r['resume_token']})
        report={'status':'PASS','mode':'real Windows injected F24 input to owned foreground fixture; not a human keyboard test',
          'paused_before_finishing':len(r['completed'])<80,'unacknowledged_resume_denied':True,'cancelled':cancelled['status'],'result':r}
        (ROOT/'gui_delegate/reports/takeover.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=True,indent=2))
    finally:
        if win32gui.IsWindow(hwnd):win32gui.PostMessage(hwnd,0x10,0,0)
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.terminate()
if __name__=='__main__':asyncio.run(main())
