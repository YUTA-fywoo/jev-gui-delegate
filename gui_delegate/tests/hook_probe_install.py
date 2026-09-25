import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jev_client import ROOT
from manage import codex_home,backup
path=codex_home()/"hooks.json";doc=json.loads(path.read_text("utf-8"));backup(path)
entry={"matcher":".*","hooks":[{"type":"command","command":"C:/jev/jev-bridge/.venv/Scripts/python.exe C:/jev/jev-bridge/gui_delegate/tests/hook_name_probe.py","timeout":3,"statusMessage":"Temporary read-only tool-name probe"}]}
items=doc["hooks"]["PreToolUse"]
if sys.argv[1]=="install":
    if entry not in items:items.append(entry)
else:doc["hooks"]["PreToolUse"]=[x for x in items if x!=entry]
path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),"utf-8")
print("temporary hook "+sys.argv[1])
