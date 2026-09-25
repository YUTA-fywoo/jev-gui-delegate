import asyncio
import json
import subprocess
import sys
import time
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jev_client import ROOT
from gui_delegate.service import run_task,cancel_task
from gui_delegate.schema import Contract
from gui_delegate.drivers import Windows

def probe(report_path=None):
    import win32gui
    p=subprocess.Popen([sys.executable,str(ROOT/"gui_delegate/fixtures/native.py")],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    pid,hwnd=map(int,p.stdout.readline().split())
    c={"goal":"Fill and verify a synthetic Windows draft","language":"mixed",
       "target":{"driver":"windows","hwnd":hwnd,"process_id":pid,"executable":sys._base_executable,"window_title":"Jev Delegate Native Fixture"},
       "scope":{"programs":[sys._base_executable],"actions":["fill","click","read"],"read_roots":[str(ROOT/"gui_delegate/fixtures")]},
       "inputs":{"text":{"value":"中文测试\r\n日本語テスト & < > \" ' \\ $"}},
       "steps":[{"id":"fill","intent":"Fill the owned test edit","op":"fill","target":{"role":"Edit","automation_id":"101"},"input_ref":"text","effect":"local",
                 "after":[{"kind":"value","target":{"role":"Edit","automation_id":"101"},"input_ref":"text"}]},
                {"id":"save","intent":"保存 test draft","op":"click","target":{"role":"Button","name":"保存"},"effect":"local",
                 "after":[{"kind":"text","target":{"role":"Text","automation_id":"103"},"equals":"保存済み: 中文测试\r\n日本語テスト & < > \" ' \\ $"}]}],
       "success":[{"kind":"value","target":{"role":"Edit","automation_id":"101"},"input_ref":"text"}],"budget":{"seconds":35}}
    report={k:{"status":"BLOCKED","reason":"PRIOR_STAGE_NOT_COMPLETED"} for k in ("native_cjk","file_dialog","save_dialog")}
    try:
        r=asyncio.run(run_task(c));report["native_cjk"]=r
        if r["status"]!="completed":
            asyncio.run(cancel_task({"resume_token":r["resume_token"]}));return report
        d=Windows(Contract.model_validate(c));d.open()
        buttons=[w for w in d.window.descendants() if w.element_info.automation_id=="104"]
        buttons[0].invoke();time.sleep(0.5)
        obs=d.observe()
        # Only synthetic common-dialog control names are inspected, never production windows.
        report["dialog_controls"]={"structured_count":len(obs.controls),"source":"owned test common dialog; labels retained only in DPAPI observations"}
        file_query={"role":"Edit","automation_id":"1148"}
        edits=[x for x in obs.controls if x.role=="Edit"]
        filename=[x for x in edits if x.automation_id=="1148"]
        if not filename:filename=[x for x in edits if "文件名" in x.name or "File name" in x.name]
        if len(filename)!=1:
            report["file_dialog"]={"status":"BLOCKED","reason":"FILENAME_CONTROL_NOT_UNIQUE"}
        else:
            file_query={"role":"Edit","automation_id":filename[0].automation_id,"name":filename[0].name}
            open_buttons=[x for x in obs.controls if x.role in ("Button","SplitButton") and x.automation_id=="1" and (x.name.startswith("打开") or x.name.startswith("Open") or x.name.startswith("開く"))]
            if len(open_buttons)!=1:report["file_dialog"]={"status":"BLOCKED","reason":"OPEN_BUTTON_NOT_UNIQUE"}
            else:
                file_path=str(ROOT/"gui_delegate/fixtures/sample.txt")
                c["inputs"]["file"]={"kind":"path","value":file_path}
                c["steps"]=[{"id":"filename","intent":"Fill the synthetic fixture filename","op":"fill","target":file_query,"input_ref":"file","effect":"local","after":[{"kind":"value","target":file_query,"input_ref":"file"}]},
                   {"id":"open","intent":"Choose this fixture file","op":"click","target":{"role":open_buttons[0].role,"name":open_buttons[0].name,"automation_id":open_buttons[0].automation_id},"effect":"local","after":[{"kind":"text","target":{"role":"Text","automation_id":"105"},"equals":file_path}]}]
                c["success"]=c["steps"][-1]["after"]
                r=asyncio.run(run_task(c));report["file_dialog"]=r
                if r["status"]!="completed":
                    asyncio.run(cancel_task({"resume_token":r["resume_token"]}));return report
        output=ROOT/'gui_delegate/reports/native-saved.txt'
        if output.exists():
            assert output.read_text('utf-8')=='Synthetic native save fixture.';output.unlink()
        d=Windows(Contract.model_validate(c));d.open()
        [w for w in d.window.descendants() if w.element_info.automation_id=='106'][0].invoke();time.sleep(.5)
        obs=d.observe();edits=[x for x in obs.controls if x.role=='Edit' and x.automation_id=='1001']
        if not edits:edits=[x for x in obs.controls if x.role=='Edit' and ('文件名' in x.name or 'File name' in x.name)]
        buttons=[x for x in obs.controls if x.role in ('Button','SplitButton') and x.automation_id=='1']
        if len(edits)!=1 or len(buttons)!=1:report['save_dialog']={'status':'BLOCKED','reason':'SAVE_DIALOG_CONTROL_NOT_UNIQUE'}
        else:
            filename_query={'role':'Edit','name':edits[0].name,'automation_id':edits[0].automation_id}
            c['scope']['write_roots']=[str(output.parent)];c['inputs']['output']={'kind':'path','value':str(output)}
            c['steps']=[{'id':'filename','intent':'Fill the designated synthetic output filename','op':'fill','effect':'local','target':filename_query,'input_ref':'output','after':[{'kind':'value','target':filename_query,'input_ref':'output'}]},
              {'id':'save_file','intent':'Save the owned synthetic fixture only','op':'click','effect':'local','target':{'role':buttons[0].role,'name':buttons[0].name,'automation_id':'1'},'after':[{'kind':'file','input_ref':'output'}]}]
            c['success']=[{'kind':'file','input_ref':'output'}]
            r=asyncio.run(run_task(c));report['save_dialog']=r
            if r['status']!='completed':asyncio.run(cancel_task({'resume_token':r['resume_token']}))
            else:assert output.read_text('utf-8')=='Synthetic native save fixture.'
    except Exception as exc:
        report["probe_error"]={"status":"FAIL","type":type(exc).__name__}
    finally:
        (report_path or ROOT/"gui_delegate/reports/native.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),"utf-8")
        win32gui.PostMessage(hwnd,0x0010,0,0)
        try:p.wait(timeout=4)
        except subprocess.TimeoutExpired:p.terminate()
    (report_path or ROOT/"gui_delegate/reports/native.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),"utf-8")
    return report

if __name__=="__main__":print(json.dumps({k:v for k,v in probe().items() if k!='dialog_controls'},ensure_ascii=False,indent=2))
