"""Migrate only this install's owned hook definition; leave unrelated hooks unchanged."""
import json
from pathlib import Path
from .install import STATE
from manage import backup
state=json.loads(STATE.read_text('utf-8'));path=Path(state['hooks']);doc=json.loads(path.read_text('utf-8'))
old=state['hook_entry'];new=json.loads(json.dumps(old));new['matcher']='^(mcp__cua_repl[._]+js|mcp__node_repl[._]+js|cua_repl[.]js|node_repl[.]js|Bash)$'
new['hooks'][0]['command']='C:/jev/jev-bridge/.venv/Scripts/python.exe C:/jev/jev-bridge/gui_delegate/hook.py'
backup(path)
entries=doc['hooks']['PreToolUse'];assert old in entries
entries[entries.index(old)]=new;path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),'utf-8')
state['hook_entry']=new;STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf-8')
print('Owned narrow matcher updated; normal trust review required again.')
