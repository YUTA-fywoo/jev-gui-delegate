import asyncio,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jev_client import ROOT
from gui_delegate.service import run_task,cancel_task
from gui_delegate.schema import Contract
from gui_delegate.drivers import Windows

async def main():
    import win32gui
    p=subprocess.Popen([sys.executable,str(ROOT/'gui_delegate/fixtures/native.py')],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    pid,hwnd=map(int,p.stdout.readline().split())
    try:
        c={'goal':'Verify native slider and list scroll after moving only the owned test window',
           'target':{'driver':'windows','hwnd':hwnd,'process_id':pid,'executable':sys._base_executable,'window_title':'Jev Delegate Native Fixture'},
           'scope':{'programs':[sys._base_executable],'actions':['range','scroll']},'inputs':{'number':{'value':'7'}},
           'steps':[{'id':'range','op':'range','intent':'Set fixture slider','effect':'local','target':{'role':'Slider','automation_id':'110'},'input_ref':'number',
              'after':[{'kind':'value','target':{'role':'Slider','automation_id':'110'},'input_ref':'number'}]}],
           'success':[{'kind':'value','target':{'role':'Slider','automation_id':'110'},'input_ref':'number'}],'budget':{'seconds':35}}
        win32gui.SetWindowPos(hwnd,0,320,220,810,600,0x14)
        d=Windows(Contract.model_validate(c));d.open();obs=d.observe()
        lists=[x for x in obs.controls if x.automation_id=='111']
        if len(lists)==1 and lists[0].value is not None:
            q={'role':lists[0].role,'automation_id':'111'}
            condition={'kind':'value','target':q,'equals':0,'comparison':'gt'}
            c['steps'].append({'id':'scroll','op':'scroll','intent':'Scroll owned native list','effect':'local','target':q,'after':[condition]});c['success'].append(condition)
        r=await run_task(c)
        if r['status']!='completed':await cancel_task({'resume_token':r['resume_token']})
        report={'status':'PASS' if r['status']=='completed' else 'FAIL','native_scroll_available':len(c['steps'])==2,'owned_window_moved_and_resized':True,'result':r}
        (ROOT/'gui_delegate/reports/native-patterns.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=True,indent=2))
        assert report['status']=='PASS'
    finally:
        if win32gui.IsWindow(hwnd):win32gui.PostMessage(hwnd,0x10,0,0)
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.terminate()
if __name__=='__main__':asyncio.run(main())
