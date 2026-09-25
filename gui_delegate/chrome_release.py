"""Conflict-checked, reversible source/owned-skill release switch. No browser action."""
import argparse,hashlib,json,os,tempfile,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'gui_delegate/reports/chrome-complete-20260923'

def sha(data):return hashlib.sha256(data).hexdigest() if data is not None else None

def apply(version,dry=False,release=None):
    report=REPORT if release is None else ROOT/'gui_delegate/reports'/release
    if report.resolve().parent!=(ROOT/'gui_delegate/reports').resolve():raise RuntimeError('RELEASE_PATH_DENIED')
    plan=json.loads((report/'rollback-plan.json').read_text('utf-8'))
    skill=Path(plan['skill']).resolve()
    if skill!=(Path.home()/'.agents/skills/jev-gui-delegate').resolve():raise RuntimeError('SKILL_PATH_DENIED')
    allowed=[ROOT,skill]
    manifest=Path(plan['manifest']).resolve()
    from manage import codex_home
    if manifest!=(codex_home()/'jev-integration.json').resolve():raise RuntimeError('MANIFEST_PATH_DENIED')
    global_paths={manifest}
    if plan.get('rules'):
        rules=Path(plan['rules']).resolve()
        if rules not in {codex_home()/'AGENTS.md',codex_home()/'AGENTS.override.md'}:raise RuntimeError('RULES_PATH_DENIED')
        global_paths.add(rules)
    prepared=[]
    with zipfile.ZipFile(report/'rollback-payload.zip') as archive:
        for row in plan['files']:
            path=Path(row['path']);resolved=path.resolve()
            if resolved not in global_paths and not any(resolved.is_relative_to(r) for r in allowed):raise RuntimeError('ROLLBACK_PATH_DENIED')
            if any(p.exists() and (p.is_symlink() or getattr(p.stat(follow_symlinks=False),'st_file_attributes',0)&0x400) for p in [path,*path.parents]):raise RuntimeError('ROLLBACK_REPARSE_DENIED')
            current=sha(path.read_bytes()) if path.exists() else None
            if current not in (row['before_sha256'],row['after_sha256']):raise RuntimeError('LOCAL_EDITS_PRESERVED: '+str(path))
            entry=row[version+'_entry'];data=archive.read(entry) if entry else None
            if sha(data)!=row[version+'_sha256']:raise RuntimeError('ROLLBACK_ARCHIVE_HASH_MISMATCH')
            prepared.append((path,data,current))
    changed=0
    if not dry:
        for path,data,current in prepared:
            if current==sha(data):continue
            if data is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.jev-release-',delete=False) as handle:
                    handle.write(data);temporary=Path(handle.name)
                os.replace(temporary,path)
            changed+=1
        for path,data,_ in prepared:
            if (sha(path.read_bytes()) if path.exists() else None)!=sha(data):raise RuntimeError('ROLLBACK_VERIFICATION_FAILED')
    return {'status':'PASS','release':version,'checked_files':len(prepared),'changed_files':changed,'dry_run':dry,
            'browser_or_credentials_changed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['rollback','restore','check']);p.add_argument('--release');args=p.parse_args()
    print(json.dumps(apply('before' if args.action=='rollback' else 'after',args.action=='check',args.release)))
