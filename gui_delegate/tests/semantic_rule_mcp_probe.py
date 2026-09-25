"""Fresh configured stdio MCP workers, owned browser and native widgets."""
import asyncio,html,json,os,tomllib
from concurrent.futures import ThreadPoolExecutor
from mcp import ClientSession
from mcp.client.stdio import stdio_client,StdioServerParameters
from manage import codex_home
from jev_client import ROOT
from gui_delegate.daily_calibration import Fixture
from gui_delegate.kind_repair_evaluation import read,write
from gui_delegate import semantic_rules as rules

async def main():
    cfg=tomllib.loads((codex_home()/'config.toml').read_text('utf-8'))['mcp_servers']['jev-bridge']
    allowed={'PATH','SYSTEMROOT','WINDIR','SYSTEMDRIVE','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA'}
    env={k:v for k,v in os.environ.items() if k.upper() in allowed};env.update(cfg['env'])
    for name in cfg.get('env_vars',[]):
        if os.environ.get(name):env[name]=os.environ[name]
    params=StdioServerParameters(command=cfg['command'],args=cfg['args'],cwd=cfg['cwd'],env=env)
    fixture=Fixture();pool=ThreadPoolExecutor(max_workers=1);results=[]
    cases=[c for c in read('cases') if c['variant']=='normal' and
          (c['driver'],c['language'],c['family']) in [('browser','zh','file_picker'),('browser','en','folder_picker'),('windows','ja','help_guide'),('windows','ja','about_application')]]
    try:
        with open(os.devnull,'w') as err:
            async with stdio_client(params,errlog=err) as (r,w):
                async with ClientSession(r,w,read_timeout_seconds=55) as session:
                    await session.initialize();listed=await session.list_tools()
                    assert {'run_task','resume_task','cancel_task','diagnose_task'}<={t.name for t in listed.tools}
                    caps=(await session.call_tool('diagnose_task',{})).structured_content
                    assert caps['semantic_rules']['enabled'] and caps['semantic_rules']['rules_sha256']==rules.fingerprint()
                    for case in cases:
                        c,d=await asyncio.get_running_loop().run_in_executor(pool,fixture.prepare,case)
                        if case['driver']=='browser':
                            path=ROOT/'gui_delegate/fixtures/semantic-kind-mcp.html'
                            buttons=''.join('<button type="button" onclick="document.querySelector(\'output\').textContent=this.textContent">'+html.escape(label)+'</button>' for label in case['labels'])
                            path.write_text('<meta charset="utf-8"><main>'+buttons+'</main><output role="status" aria-label="Outcome">Pending</output>','utf-8')
                            c.target.url=path.as_uri()
                        result=(await session.call_tool('run_task',c.model_dump())).structured_content
                        if result['status']!='completed':await session.call_tool('cancel_task',{'resume_token':result['resume_token']})
                        assert result['status']=='completed',{'case':case['id'],'reason':result['escalation_reason']}
                        assert result['usage']['semantic_alias_decisions']==1 and result['usage']['jev_requests']==0
                        assert result['usage']['deterministic_decisions']==1 and all(v['passed'] for v in result['verification'])
                        results.append({'case':case['id'],'status':result['status'],'usage':result['usage'],'verification':result['verification']})
    finally:
        await asyncio.get_running_loop().run_in_executor(pool,fixture.close);pool.shutdown()
    report={'status':'PASS','fresh_registered_stdio_mcp':True,'tools_list':'PASS','rules':caps['semantic_rules'],'tasks':results}
    write('mcp-rules',report);print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':asyncio.run(main())
