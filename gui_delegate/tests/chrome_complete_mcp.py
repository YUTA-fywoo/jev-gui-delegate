"""Probe the real registered stdio server without opening any browser or desktop."""
import asyncio,json,os,tomllib
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import stdio_client,StdioServerParameters
from manage import codex_home
from jev_client import ROOT

async def main(report=None):
    cfg=tomllib.loads((codex_home()/'config.toml').read_text('utf-8'))['mcp_servers']['jev-bridge']
    allowed={'PATH','SYSTEMROOT','WINDIR','SYSTEMDRIVE','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA'}
    env={k:v for k,v in os.environ.items() if k.upper() in allowed};env.update(cfg['env'])
    for name in cfg['env_vars']:
        if os.environ.get(name):env[name]=os.environ[name]
    params=StdioServerParameters(command=cfg['command'],args=cfg['args'],cwd=cfg['cwd'],env=env)
    with open(os.devnull,'w') as err:
        async with stdio_client(params,errlog=err) as (r,w):
            async with ClientSession(r,w,read_timeout_seconds=30) as s:
                await s.initialize();tools=(await s.list_tools()).tools
                names=sorted(t.name for t in tools);assert set(names)==set(cfg['enabled_tools'])
                schema=next(t.input_schema for t in tools if t.name=='run_task')
                assert 'contract_path' in schema['properties'] and 'steps' in schema['properties']
                from gui_delegate.schema import Contract
                full=Contract.model_json_schema()
                assert 'upload_refs' in full['$defs']['BrowserOptions']['properties']
                assert 'viewport_set' in full['$defs']['Step']['properties']['op']['enum']
                caps=(await s.call_tool('diagnose_task',{})).structured_content
                assert caps['version']=='0.4.3' and 'upload' in caps['official_chrome']['supported_operations']
                health=(await s.call_tool('health',{})).structured_content
                assert health.get('credential_available'),health
                invalid=await s.call_tool('run_task',{'goal':'synthetic invalid contract'})
                assert invalid.is_error
                result={'status':'PASS','transport':'actual registered MCP stdio child',
                    'tools':names,'new_schema':True,'credential_available_to_child':True,
                    'capabilities_version':caps['version'],'invalid_schema_rejected':True,
                    'browser_control_via_mcp_alone':False}
    ((report or ROOT/'gui_delegate/reports/current-verification')/'mcp.json').write_text(json.dumps(result,indent=2),'utf-8')
    if report is None:print(json.dumps(result))
    return result

if __name__=='__main__':asyncio.run(main())
