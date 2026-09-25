"""Reversible official-Chrome route switch; no credentials or browser changes."""
import argparse,json,os
from .security import Stop
from jev_client import ROOT
from manage import backup,codex_home

POLICY=ROOT/'gui_delegate/chrome-session-policy.json'
RUNTIME=ROOT/'gui_delegate/chrome-runtime.json'
ENV_KEYS=('PATH','SYSTEMROOT','SYSTEMDRIVE','WINDIR','PROGRAMFILES','PROGRAMFILES(X86)',
          'PROGRAMW6432','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA')

def describe():
    try:enabled=json.loads(POLICY.read_text('utf-8')).get('enabled') is True
    except (OSError,ValueError):enabled=False
    return {'enabled':enabled,'transport':'official Chrome Browser Use API + anonymous stdio',
            'requires_active_codex_browser_session':True,'physical_input_injection':False,
            'policy':str(POLICY),'module':str(ROOT/'gui_delegate/chrome_delegate.mjs')}

def require_enabled():
    if not describe()['enabled']:raise Stop('CHROME_ROUTE_DISABLED','blocked')

def set_enabled(value):
    if POLICY.exists():backup(POLICY)
    POLICY.write_text(json.dumps({'version':1,'enabled':bool(value)},indent=2),'utf-8')
    # Only explicitly listed process-launch fields. Never serialize the general environment.
    if value:
        if RUNTIME.exists():backup(RUNTIME)
        RUNTIME.write_text(json.dumps({'env':{k:os.environ[k] for k in ENV_KEYS if k in os.environ}},ensure_ascii=False,indent=2),'utf-8')
    manifest=codex_home()/'jev-integration.json'
    if manifest.exists():
        data=json.loads(manifest.read_text('utf-8'))
        if 'official_chrome' in data.get('gui_delegate',{}):
            backup(manifest);data['gui_delegate']['official_chrome']['enabled']=bool(value)
            manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    return describe()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['status','enable','disable']);a=p.parse_args()
    print(json.dumps(describe() if a.action=='status' else set_enabled(a.action=='enable'),ensure_ascii=True,indent=2))
