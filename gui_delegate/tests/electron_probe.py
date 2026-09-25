import asyncio,json,os,subprocess,sys,time,queue,threading,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jev_client import ROOT
from gui_delegate.service import run_task,cancel_task
from gui_delegate.schema import Contract
from gui_delegate.drivers import Windows

async def main():
    folder=ROOT/'gui_delegate/fixtures/electron';exe=folder/'node_modules/electron/dist/electron.exe'
    env=dict(os.environ);env.pop('ELECTRON_RUN_AS_NODE',None)
    p=subprocess.Popen([str(exe),str(folder)],cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
    q=queue.Queue()
    def read():
        for line in p.stdout:
            try:q.put(json.loads(line))
            except ValueError:pass
    threading.Thread(target=read,daemon=True).start()
    ident=q.get(timeout=25)
    import win32gui
    try:
        c={'goal':'Fill and verify isolated Electron application through Windows UIA',
          'target':{'driver':'windows','hwnd':ident['hwnd'],'process_id':ident['pid'],'executable':str(exe),'window_title':'Jev Isolated Electron Fixture'},
          'scope':{'programs':[str(exe)],'actions':['fill','click']},'inputs':{'text':{'value':'Electron 中文 日本語 & < >'}},
          'steps':[{'id':'fill','op':'fill','intent':'Fill synthetic Electron field','target':{'role':'Edit','name':'内容'},'input_ref':'text','effect':'local','after':[{'kind':'value','target':{'role':'Edit','name':'内容'},'input_ref':'text'}]}],
          'success':[{'kind':'value','target':{'role':'Edit','name':'内容'},'input_ref':'text'}],'budget':{'seconds':45}}
        await asyncio.sleep(.8)
        c['steps'].append({'id':'save','op':'click','intent':'Save only in the isolated fixture','target':{'role':'Button','name':'保存テスト'},'effect':'local',
          'after':[{'kind':'text','target':{'role':'Text','name':c['inputs']['text']['value']},'equals':c['inputs']['text']['value']}]})
        c['success']+=c['steps'][-1]['after']
        d=Windows(Contract.model_validate(c));d.open();obs=d.observe()
        result=await run_task(c)
        if result['status']!='completed':await cancel_task({'resume_token':result['resume_token']})
        # Transfer the actual observed value to a different native program without
        # sending that value to Jev or requiring a main-model decision between steps.
        native=subprocess.Popen([sys.executable,str(ROOT/'gui_delegate/fixtures/native.py')],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        npid,nhwnd=map(int,native.stdout.readline().split())
        try:
            c['targets']={'native':{'driver':'windows','hwnd':nhwnd,'process_id':npid,'executable':sys._base_executable,'window_title':'Jev Delegate Native Fixture'}}
            c['scope']['programs'].append(sys._base_executable);c['scope']['actions']+=['copy','paste'];c['inputs']['copied']={'value':'','captured':True}
            source={'role':'Edit','name':'内容'};dest={'role':'Edit','automation_id':'101'}
            c['steps']=[{'id':'copy','op':'copy','intent':'Copy only the synthetic Electron field','target':source,'output_ref':'copied','after':[{'kind':'value','target':source,'input_ref':'copied'}]},
              {'id':'paste','surface':'native','op':'paste','intent':'Paste synthetic data in the exact native window','target':dest,'input_ref':'copied','effect':'local','after':[{'surface':'native','kind':'value','target':dest,'input_ref':'copied'}]}]
            c['success']=[{'kind':'value','target':source,'input_ref':'text'},*c['steps'][-1]['after']]
            cross=await run_task(c)
            if cross['status']!='completed':await cancel_task({'resume_token':cross['resume_token']})
        finally:
            if win32gui.IsWindow(nhwnd):win32gui.PostMessage(nhwnd,0x10,0,0)
            native.wait(timeout=5)
        report={'status':'PASS' if result['status']=='completed' and cross['status']=='completed' else 'FAIL','cross_application_result':cross,'electron_version':(exe.parent/'version').read_text().strip(),
          'source':'https://github.com/electron/electron','lock':str(folder/'package-lock.json'),'sandbox':True,'production_profile_used':False,
          'structured_controls':len(obs.controls),'result':result,'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
        (ROOT/'gui_delegate/reports/electron.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
        print(json.dumps(report,ensure_ascii=True,indent=2));assert report['status']=='PASS'
    finally:
        if win32gui.IsWindow(ident['hwnd']):win32gui.PostMessage(ident['hwnd'],0x10,0,0)
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.terminate()

if __name__=='__main__':asyncio.run(main())
