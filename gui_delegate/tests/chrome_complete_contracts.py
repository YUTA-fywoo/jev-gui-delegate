import copy,json,uuid
from pathlib import Path
from jev_client import ROOT
from gui_delegate.schema import Contract
from gui_delegate.security import validate_contract

REPORT=ROOT/'gui_delegate/reports/chrome-complete-20260923'
def q(role,name,frame=None):
    return {'role':role,'name':name,**({'frame_url':frame} if frame else {})}
def pred(kind,target=None,equals=None,ref=None,surface='main'):
    return {'kind':kind,**({'target':target} if target else {}),**({'input_ref':ref} if ref else {'equals':equals}),'surface':surface}
def step(ident,op,target,after,ref=None,**extra):
    return {'id':ident,'op':op,'intent':op+' the synthetic test control','effect':'local','target':target,'after':after,**({'input_ref':ref} if ref else {}),**extra}
def build():
    f=json.loads((REPORT/'fixture.json').read_text('utf-8'));origin=f['origin'];url=f['url'];frame=f['frame_origin']+'/frame'
    output=REPORT/('artifacts-'+uuid.uuid4().hex[:8]);output.mkdir()
    upload=output/'synthetic-upload.txt';upload.write_text('SYNTHETIC UPLOAD\n中文 日本語\n','utf-8')
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
        downloads=Path(__import__('os').path.expandvars(winreg.QueryValueEx(key,'{374DE290-123F-4565-9164-39C4925E467B}')[0]))
    base={'goal':'Verify only locally generated synthetic Chrome fixtures','target':{'driver':'browser','connection':'official_chrome','tab_id':'new-tab-preflight','url':url,'headless':False},'language':'mixed',
      'scope':{'origins':[origin,f['frame_origin']],'read_roots':[str(output),str(downloads)],'write_roots':[str(output)],'actions':['read']},
      'inputs':{'chinese':{'value':'中文测试 张三'},'japanese':{'value':'日本語の入力\n特殊文字 ! @ # & < >'},'range':{'value':'7'},'file':{'kind':'path','value':str(upload)}},
      'steps':[],'success':[],'budget':{'seconds':180,'steps':60,'jev_calls':2},'authorizations':[]}
    cases={}
    def emit(name,steps,extra=None):
        c=copy.deepcopy(base);c['steps']=steps;c['success']=copy.deepcopy(steps[-1]['after']);c['scope']['actions']=list(dict.fromkeys(s['op'] for s in steps))
        if extra:c.update(extra)
        for s in steps:
            if s['op'] in ('upload','dialog_accept') or s.get('effect')=='submit':
                c['authorizations'].append({'step_id':s['id'],'effect':s['effect'],'target_name':s.get('target',{}).get('name','') if s.get('target') else '', 'destination':url,'user_instruction':'Test only this generated local synthetic fixture action and designated synthetic file.'})
        validate_contract(Contract.model_validate(c));c['target'].pop('tab_id');cases[name]=c
    emit('frames-shadow',[
      step('name','fill',q('textbox','中文输入'),[pred('value',q('textbox','中文输入'),ref='chinese')],'chinese'),
      step('memo','fill',q('textbox','メモ'),[pred('value',q('textbox','メモ'),ref='japanese')],'japanese'),
      step('frame-fill','fill',q('textbox','框架输入',frame),[pred('value',q('textbox','框架输入',frame),ref='chinese')],'chinese'),
      step('frame-click','click',q('button','Frame action',frame),[pred('text',q('status','Frame state',frame),'Frame done')]),
      step('shadow-fill','fill',q('textbox','Shadow input'),[pred('value',q('textbox','Shadow input'),ref='japanese')],'japanese'),
      step('shadow-click','click',q('button','Shadow action'),[pred('text',q('status','Shadow state'),'Shadow done')]),
    ])
    emit('range-double-hover',[
      step('range','range',q('slider','Volume'),[pred('value',q('slider','Volume'),ref='range')],'range'),
      step('double','double_click',q('button','Double action'),[pred('text',q('status','Double state'),'Double done')]),
      step('hover','hover',q('button','Hover action'),[pred('text',q('status','Hover state'),'Hover done')])])
    emit('scroll-drag',[
      step('scroll','scroll',q('region','Scroll area'),[{'kind':'attribute','attribute':'scrollTop','target':q('region','Scroll area'),'comparison':'gt','equals':0}]),
      step('bottom','click',q('button','Bottom action'),[pred('text',q('status','Bottom state'),'Bottom done')]),
      step('drag','drag',q('button','Drag item'),[pred('text',q('status','Drag state'),'Dropped once')],destination=q('button','Drop zone'))])
    emit('upload',[
      step('choose-file','upload',q('file','Attachment'),[pred('text',q('status','File state'),upload.name)],'file'),
      step('upload-file','click',q('button','Upload synthetic'),[pred('text',q('status','Upload state'),'Upload verified')],effect='submit')])
    download_ref={'kind':'path','value':str(output/'verified-download.txt')}
    emit('download',[step('download','download',q('link','Download synthetic'),[pred('file',ref='download')],'download',browser_options={'expected_download_name':f['download_name'],'download_directory':str(downloads)})],{'inputs':{**base['inputs'],'download':download_ref}})
    inputs={**base['inputs'],'dest':{'value':origin+'/destination'},'features':{'value':url},'clip':{'value':'virtual clipboard 中文 日本語'},**{k:{'kind':'path','value':str(output/(k+ext))} for k,ext in [('screenshot','.png'),('export','.md'),('logs','.json'),('assets','.json'),('clipboard','.txt')]}}
    emit('navigation-tabs',[
      step('navigate','navigate',None,[pred('url',equals=origin+'/destination')],'dest'),
      step('back','back',None,[pred('url',equals=url)]),step('forward','forward',None,[pred('url',equals=origin+'/destination')]),
      step('reload','reload',None,[pred('text',q('status','Destination'),'Arrived')]),
      step('new','new_tab',None,[pred('url',equals=url)],'features'),
      step('switch','switch_tab',None,[pred('url',equals=origin+'/destination')],'dest'),
      step('switch-back','switch_tab',None,[pred('url',equals=url)],'features'),
      step('close','close_tab',None,[pred('tab_count',equals=1)])],{'inputs':inputs})
    for name in ['screenshot','export','logs','assets','clipboard']:
        steps=[step(name,name if name!='clipboard' else 'clipboard_read',None,[pred('file',ref=name)],name)]
        if name=='clipboard':steps.insert(0,step('clipboard-write','clipboard_write',None,[pred('exists',q('status','Jev artifact clipboard-write'))],'clip'))
        emit(name,steps,{'inputs':inputs})
    emit('dialog-dismiss',[
      step('open','click',q('button','Open alert'),[pred('exists',q('dialog','alert'))]),
      step('dismiss','dialog_dismiss',None,[pred('absent',q('dialog','alert'))])])
    emit('dialog-accept',[
      step('open','click',q('button','Open confirm'),[pred('exists',q('dialog','confirm'))]),
      step('accept','dialog_accept',None,[pred('text',q('status','Dialog state'),'Accepted')])])
    multi_steps=[step('copy-source','fill',q('textbox','中文输入'),[pred('value',q('textbox','中文输入'),ref='chinese')],'chinese'),
       step('copy','copy',q('textbox','中文输入'),[pred('value',q('textbox','中文输入'),ref='chinese')],output_ref='captured'),
       step('paste','paste',q('textbox','中文输入'),[pred('value',q('textbox','中文输入'),ref='captured',surface='second')],'captured',surface='second')]
    emit('named-surfaces',multi_steps,{'inputs':{**base['inputs'],'captured':{'value':'','captured':True}},'targets':{'second':copy.deepcopy(base['target'])}})
    (REPORT/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf-8')
    (REPORT/'test-files.json').write_text(json.dumps({'output':str(output),'upload':str(upload),'downloads':str(downloads),'download_name':f['download_name']},ensure_ascii=False,indent=2),'utf-8')
    return list(cases)
if __name__=='__main__':print(json.dumps(build()))
