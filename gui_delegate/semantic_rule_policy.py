"""Local version-bound activation; only an operator CLI changes it."""
import argparse,json,os
from pathlib import Path
from . import semantic_rules as rules

PATH=Path(__file__).with_name('semantic-rule-policy.json')
def load(path=PATH):
    try:
        d=json.loads(path.read_text('utf-8'))
        if set(d)!={'enabled','version','rules_sha256'} or type(d['enabled']) is not bool:return None
        if d['version']!=rules.VERSION or d['rules_sha256']!=rules.fingerprint():return None
        return d
    except (OSError,ValueError):return None
def active():
    d=load();return bool(d and d['enabled'])
def describe():
    d=load()
    return {'enabled':bool(d and d['enabled']),'version':rules.VERSION,'rules_sha256':rules.fingerprint(),
            'scope':'approved button aliases for file/folder picker and help/about intents; low-risk semantic clicks only',
            'policy_valid':d is not None,'automatic_updates':False}
def set_enabled(enabled):
    from manage import backup
    d=load()
    if d is None:raise RuntimeError('Missing or modified rule policy; preserving user changes')
    if d['enabled']==enabled:return describe()
    backup(PATH);d['enabled']=enabled
    temp=PATH.with_suffix('.tmp');temp.write_text(json.dumps(d,indent=2)+'\n','utf-8');os.replace(temp,PATH)
    return describe()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['enable','disable','status']);a=p.parse_args()
    print(json.dumps(describe() if a.action=='status' else set_enabled(a.action=='enable'),indent=2))
