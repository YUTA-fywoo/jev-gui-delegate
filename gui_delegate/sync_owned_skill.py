import hashlib,json,shutil
from pathlib import Path
from .install import STATE,BASE
from manage import backup
state=json.loads(STATE.read_text('utf-8'));destination=Path(state['skill'])
for name,expected in state['skill_hashes'].items():
    target=destination/name
    assert hashlib.sha256(target.read_bytes()).hexdigest()==expected,'User skill edits preserved'
for source in (BASE/'skill').rglob('*'):
    if source.is_file():
        target=destination/source.relative_to(BASE/'skill');target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():backup(target)
        shutil.copyfile(source,target)
state['skill_hashes']={str(p.relative_to(destination)):hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.rglob('*') if p.is_file()}
STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf-8')
print('Owned skill updated with conflict checks and backups.')
