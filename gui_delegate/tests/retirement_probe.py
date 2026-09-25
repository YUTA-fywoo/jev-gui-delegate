"""Real stdio worker escalation and single-use scoped fallback, no GUI side effects."""
import asyncio,json,os,tomllib
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import stdio_client,StdioServerParameters
from manage import codex_home
from jev_client import ROOT
from gui_delegate.examples import workflow
from gui_delegate import storage
from gui_delegate.hook import bind,decide

async def probe(report):
    cfg=tomllib.loads((codex_home()/'config.toml').read_text('utf-8'))['mcp_servers']['jev-bridge']
    allowed={'PATH','SYSTEMROOT','WINDIR','SYSTEMDRIVE','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA'}
    env={k:v for k,v in os.environ.items() if k.upper() in allowed};env.update(cfg['env'])
    for name in cfg['env_vars']:
        if os.environ.get(name):env[name]=os.environ[name]
    params=StdioServerParameters(command=cfg['command'],args=cfg['args'],cwd=cfg['cwd'],env=env)
    c=workflow();c['target']={'driver':'browser','connection':'isolated','url':c['target']['url']}
    with open(os.devnull,'w') as err:
        async with stdio_client(params,errlog=err) as (r,w):
            async with ClientSession(r,w,read_timeout_seconds=30) as session:
                await session.initialize()
                result=(await session.call_tool('run_task',c)).structured_content
                assert result['status']=='escalated' and result['escalation_reason']=='LEGACY_BROWSER_RETIRED_USE_OFFICIAL_CHROME',result
                assert result['completed']==[] and result['usage'].get('actions',0)==0
                token=result['resume_token'];directory=storage.task_directory(token)
                grant=storage.read(directory/'fallback.dpapi')
                assert grant['scope']==c['scope']
                # This is a guard decision check; it does not execute a browser command.
                args={'code':f'// jev-fallback:{token}\nawait cua.getTab("synthetic-owned-tab");'}
                event={'tool_name':'mcp__cua_repl__js','session_id':'retirement-controlled-binding','tool_input':args}
                assert decide(event)['hookSpecificOutput']['permissionDecision']=='deny'
                bind(token,event['session_id'],event['tool_name'],args)
                assert decide(event)=={}
                assert decide(event)['hookSpecificOutput']['permissionDecision']=='deny'
                cancelled=(await session.call_tool('cancel_task',{'resume_token':token})).structured_content
    summary={'status':'PASS','transport':'actual registered MCP and worker',
             'old_driver_reason':result['escalation_reason'],'actions':0,'jev_requests':0,
             'scope_preserved':True,'fallback_checks':'controlled hook: reject unbound, allow exact once, reject reuse',
             'cancel_status':cancelled['status'],'os_browser_uninstalled':False}
    (report/'retirement-mcp.json').write_text(json.dumps(summary,indent=2),'utf-8')
    return summary
if __name__=='__main__':print(json.dumps(asyncio.run(probe(ROOT/'gui_delegate/reports/edge-retirement-20260923'))))
