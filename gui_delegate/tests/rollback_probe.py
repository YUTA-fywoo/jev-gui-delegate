import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import tomlkit
from jev_client import ROOT
from manage import codex_home
from gui_delegate.install import install,rollback,ROUTE
from gui_delegate import service
path=codex_home()/'config.toml';before=tomlkit.parse(path.read_text('utf-8')).unwrap()
rules=codex_home()/'AGENTS.md';rules_before=rules.read_text('utf-8')
hook_path=codex_home()/'hooks.json';hooks_before=json.loads(hook_path.read_text('utf-8'))
first=install();assert first['changed'] is False
try:
    removed=rollback();assert not service.enabled()
    after=tomlkit.parse(path.read_text('utf-8')).unwrap()
    expected=json.loads(json.dumps(before));expected['mcp_servers']['jev-bridge']['enabled_tools']=[t for t in expected['mcp_servers']['jev-bridge']['enabled_tools'] if t not in service.TOOLS]
    assert after==expected
    assert ROUTE not in rules.read_text('utf-8')
finally:restored=install()
assert service.enabled()
assert tomlkit.parse(path.read_text('utf-8')).unwrap()==before
assert rules.read_text('utf-8')==rules_before
assert json.loads(hook_path.read_text('utf-8'))==hooks_before
assert install()['changed'] is False
report={'status':'PASS','repeat_install_no_changes':True,'scoped_rollback':True,'full_semantic_restore':True,'unrelated_settings_preserved':True}
(ROOT/'gui_delegate/reports/rollback.json').write_text(json.dumps(report,indent=2),'utf-8')
print(json.dumps(report))
