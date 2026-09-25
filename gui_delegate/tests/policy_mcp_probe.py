"""Fresh registered MCP must use the persisted policy in its real worker."""
import asyncio,html,json,os,sys,tomllib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mcp import ClientSession
from mcp.client.stdio import stdio_client,StdioServerParameters
from manage import codex_home
from gui_delegate.daily_calibration import BASE,Fixture,read,write,accepted
from gui_delegate import decision_policy as dp

async def main():
    policy=dp.load();assert policy is not None
    cfg=tomllib.loads((codex_home()/'config.toml').read_text('utf-8'))['mcp_servers']['jev-bridge']
    allowed={'PATH','SYSTEMROOT','WINDIR','SYSTEMDRIVE','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA'}
    env={k:v for k,v in os.environ.items() if k.upper() in allowed};env.update(cfg['env'])
    for name in cfg.get('env_vars',[]):
        if os.environ.get(name):env[name]=os.environ[name]
    params=StdioServerParameters(command=cfg['command'],args=cfg['args'],cwd=cfg['cwd'],env=env)
    fixture=Fixture();results=[]
    # UIA/DOM setup is in the driver thread; asyncio does not execute sync Playwright here.
    from concurrent.futures import ThreadPoolExecutor
    pool=ThreadPoolExecutor(max_workers=1)
    try:
        with open(os.devnull,'w') as err:
            async with stdio_client(params,errlog=err) as (r,w):
                async with ClientSession(r,w,read_timeout_seconds=55) as session:
                    await session.initialize();caps=(await session.call_tool('diagnose_task',{})).structured_content
                    assert caps['decision_policy']==policy.id
                    for profile in policy.profiles:
                        rows=[x for x in read('holdout-rows') if (x['driver'],x['language'])==(profile.driver,profile.language) and
                          accepted(x,profile.thresholds.model_dump()) and not accepted(x,dp.DEFAULT) and x['action_verified']]
                        assert rows
                        row=rows[0];case={k:v for k,v in row.items() if k in read('cases')[0]}
                        c,d=await asyncio.get_running_loop().run_in_executor(pool,fixture.prepare,case)
                        if case['driver']=='browser':
                            # The worker owns a new browser; make the synthetic page reproducible
                            # through the contract URL instead of relying on the harness's page.
                            from jev_client import ROOT
                            path=ROOT/'gui_delegate/fixtures/calibration-policy-mcp.html'
                            buttons=''.join('<button type="button" onclick="document.querySelector(\'output\').textContent=this.textContent">'+html.escape(label)+'</button>' for label in case['labels'])
                            path.write_text('<meta charset="utf-8"><main>'+buttons+'</main><output role="status" aria-label="Outcome">Pending</output>','utf-8')
                            c.target.url=path.as_uri()
                        result=(await session.call_tool('run_task',c.model_dump())).structured_content
                        if result['status']!='completed':await session.call_tool('cancel_task',{'resume_token':result['resume_token']})
                        assert result['status']=='completed',{'case':row['id'],'reason':result['escalation_reason']}
                        assert result['usage']['decision_policy']==policy.id+':'+profile.driver+':'+profile.language
                        assert all(v['passed'] for v in result['verification'])
                        results.append({'case':row['id'],'status':result['status'],'usage':result['usage'],'verification':result['verification']})
    finally:
        await asyncio.get_running_loop().run_in_executor(pool,fixture.close);pool.shutdown()
    report={'status':'PASS','fresh_registered_stdio_mcp':True,'persisted_policy_id':policy.id,'tasks':results};write('mcp-policy',report)
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':asyncio.run(main())
