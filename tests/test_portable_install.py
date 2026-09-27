import contextlib, io, json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import manage
import install as bootstrap
from gui_delegate import install as gui
import tomlkit

class PortableInstallTests(unittest.TestCase):
    @contextlib.contextmanager
    def sandbox(self):
        with tempfile.TemporaryDirectory(prefix='jev-installer-') as folder:
            root=Path(folder)/'installation with spaces';base=root/'gui_delegate'
            user=Path(folder)/'test user';home=user/'.codex'
            source=base/'skill';source.mkdir(parents=True)
            (source/'SKILL.md').write_text('---\nname: jev-gui-delegate\ndescription: GUI delegation\n---\nC:/jev/jev-bridge\n',encoding='utf-8')
            (source/'references').mkdir()
            (source/'references/chrome.md').write_text('file:///C:/jev/jev-bridge/gui_delegate/chrome_gateway.mjs?release=0.7.0',encoding='utf-8')
            with patch.object(manage,'ROOT',root),patch.object(manage,'codex_home',lambda:home),patch.object(gui,'ROOT',root),patch.object(gui,'BASE',base),patch.object(gui,'STATE',base/'install-state.json'),patch.object(gui,'codex_home',lambda:home),patch.object(Path,'home',return_value=user),contextlib.redirect_stdout(io.StringIO()):
                manage.register()
                yield root,home,user,source

    def test_clean_install_with_no_prior_manifest_and_path_spaces(self):
        with self.sandbox() as (root,home,user,source):
            result=gui.install();self.assertTrue(result['installed'])
            skill=user/'.agents/skills/jev-gui-delegate'
            self.assertIn(root.as_uri(),(skill/'references/chrome.md').read_text('utf-8'))
            self.assertIn(root.as_posix(),(skill/'SKILL.md').read_text('utf-8'))
            manifest=json.loads((home/'jev-integration.json').read_text('utf-8'))
            self.assertEqual(manifest['gui_delegate']['version'],'0.7.0')
            hooks=json.loads((home/'hooks.json').read_text('utf-8'))
            command=hooks['hooks']['PreToolUse'][0]['hooks'][0]['command']
            self.assertIn('"',command)
            self.assertFalse(gui.install()['changed'])

    def test_owned_upgrade_preserves_unrelated_configuration(self):
        with self.sandbox() as (root,home,user,source):
            gui.install()
            config=home/'config.toml';before=config.read_bytes()
            original=(source/'SKILL.md').read_text('utf-8')
            (source/'SKILL.md').write_text(original+'\nUpdated instructions\n',encoding='utf-8')
            self.assertTrue(gui.install()['changed'])
            self.assertEqual(config.read_bytes(),before)
            self.assertIn('Updated instructions',(user/'.agents/skills/jev-gui-delegate/SKILL.md').read_text('utf-8'))

    def test_local_edits_are_not_overwritten(self):
        with self.sandbox() as (root,home,user,source):
            gui.install()
            skill=user/'.agents/skills/jev-gui-delegate/SKILL.md'
            skill.write_text('User edited skill',encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError,'local edits'):gui.install()
            self.assertEqual(skill.read_text('utf-8'),'User edited skill')

    def test_changed_codex_home_is_rejected_before_creating_configuration(self):
        with self.sandbox() as (root,home,user,source):
            gui.install()
            original=(home/'config.toml').read_bytes()
            state=(root/'gui_delegate/install-state.json').read_bytes()
            other=user/'another codex home'
            with patch.object(manage,'codex_home',lambda:other),patch.object(gui,'codex_home',lambda:other):
                with self.assertRaisesRegex(RuntimeError,'INSTALL_LOCATION_CHANGED'):manage.register()
                with self.assertRaisesRegex(RuntimeError,'INSTALL_LOCATION_CHANGED'):gui.install()
            self.assertFalse(other.exists())
            self.assertEqual((home/'config.toml').read_bytes(),original)
            self.assertEqual((root/'gui_delegate/install-state.json').read_bytes(),state)

    def test_copied_installation_is_not_silently_adopted(self):
        with self.sandbox() as (root,home,user,source):
            gui.install()
            moved=root.parent/'moved project';shutil.copytree(root,moved)
            before=(home/'config.toml').read_bytes()
            with patch.object(manage,'ROOT',moved),patch.object(gui,'ROOT',moved),patch.object(gui,'BASE',moved/'gui_delegate'),patch.object(gui,'STATE',moved/'gui_delegate/install-state.json'):
                with self.assertRaisesRegex(RuntimeError,'INSTALL_LOCATION_CHANGED'):manage.register()
                with self.assertRaisesRegex(RuntimeError,'INSTALL_LOCATION_CHANGED'):gui.install()
            self.assertEqual((home/'config.toml').read_bytes(),before)

    def test_upgrade_migrates_only_the_owned_hook_and_effective_rules(self):
        with self.sandbox() as (root,home,user,source):
            old_rules=home/'AGENTS.md';old_rules.write_text('Existing global instructions.\n',encoding='utf-8')
            gui.install()
            override=home/'AGENTS.override.md';override.write_text('User override instructions.\n',encoding='utf-8')
            hooks=home/'hooks.json';doc=json.loads(hooks.read_text('utf-8'))
            unrelated={'matcher':'OtherTool','hooks':[{'type':'command','command':'keep-user-hook'}]}
            doc['hooks']['PreToolUse'].append(unrelated)
            doc['hooks']['PreToolUse'][0]['hooks'][0]['command']=str(root/'.venv/Scripts/python.exe')+' '+str(root/'gui_delegate/hook.py')
            hooks.write_text(json.dumps(doc),encoding='utf-8')
            state_file=root/'gui_delegate/install-state.json';state=json.loads(state_file.read_text('utf-8'))
            state['hook_entry']=doc['hooks']['PreToolUse'][0]
            state_file.write_text(json.dumps(state),encoding='utf-8')
            before=(home/'config.toml').read_bytes()
            self.assertTrue(gui.install()['changed'])
            self.assertEqual((home/'config.toml').read_bytes(),before)
            self.assertIn('Existing global instructions.',old_rules.read_text('utf-8'))
            self.assertNotIn(gui.START,old_rules.read_text('utf-8'))
            self.assertTrue(override.read_text('utf-8').startswith('User override instructions.\n'))
            self.assertIn(gui.ROUTE,override.read_text('utf-8'))
            state=json.loads(state_file.read_text('utf-8'))
            self.assertEqual(state['rules'],str(override))
            current=json.loads(hooks.read_text('utf-8'))['hooks']['PreToolUse']
            self.assertEqual(current,[gui.hook_definition(),unrelated])
            self.assertFalse(gui.install()['changed'])

    def test_user_hook_edits_prevent_partial_skill_upgrade(self):
        with self.sandbox() as (root,home,user,source):
            gui.install()
            (source/'SKILL.md').write_text('Updated publisher instructions',encoding='utf-8')
            hooks=home/'hooks.json';doc=json.loads(hooks.read_text('utf-8'))
            doc['hooks']['PreToolUse'][0]['hooks'][0]['command']='user-customized-command'
            hooks.write_text(json.dumps(doc),encoding='utf-8')
            paths=[hooks,home/'AGENTS.md',home/'config.toml',root/'gui_delegate/install-state.json',user/'.agents/skills/jev-gui-delegate/SKILL.md']
            before={path:path.read_bytes() for path in paths}
            with self.assertRaisesRegex(RuntimeError,'Owned Hook missing or changed'):gui.install()
            self.assertEqual({path:path.read_bytes() for path in paths},before)

    def test_user_route_edits_are_preserved(self):
        with self.sandbox() as (root,home,user,source):
            gui.install()
            rules=home/'AGENTS.md'
            rules.write_text(rules.read_text('utf-8').replace(gui.ROUTE,gui.START+'\nUser routing preference\n'+gui.END),encoding='utf-8')
            before=rules.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'Owned route missing or edited'):gui.install()
            self.assertEqual(rules.read_bytes(),before)

    def test_scoped_rollback_and_reinstall_preserve_original_rules(self):
        with self.sandbox() as (root,home,user,source):
            rules=home/'AGENTS.md';original='User rules, including intentional spacing.\n\n'
            rules.write_text(original,encoding='utf-8');gui.install()
            unrelated={'matcher':'OtherTool','hooks':[{'type':'command','command':'keep-me'}]}
            hooks=home/'hooks.json';doc=json.loads(hooks.read_text('utf-8'))
            doc['hooks']['PreToolUse'].append(unrelated);hooks.write_text(json.dumps(doc),encoding='utf-8')
            gui.rollback()
            self.assertEqual(rules.read_text('utf-8'),original)
            self.assertEqual(json.loads(hooks.read_text('utf-8'))['hooks']['PreToolUse'],[unrelated])
            manage.register();self.assertTrue(gui.install()['installed'])
            self.assertFalse(gui.install()['changed'])

    def test_missing_registration_is_not_reported_as_installed(self):
        with self.sandbox() as (root,home,user,source):
            gui.install()
            config=home/'config.toml';doc=tomlkit.parse(config.read_text('utf-8'))
            del doc['mcp_servers']['jev-bridge'];config.write_text(tomlkit.dumps(doc),encoding='utf-8')
            before=config.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'MCP registration missing or changed'):gui.install()
            self.assertEqual(config.read_bytes(),before)

    def test_missing_ownership_record_is_an_explicit_preserved_conflict(self):
        with self.sandbox() as (root,home,user,source):
            gui.install();(root/'reports/registration.json').unlink()
            before=(home/'config.toml').read_bytes()
            with self.assertRaisesRegex(RuntimeError,'REGISTRATION_OWNERSHIP_MISSING'):manage.register()
            self.assertEqual((home/'config.toml').read_bytes(),before)

    def test_owned_mcp_upgrade_preserves_other_entries_and_comments(self):
        with self.sandbox() as (root,home,user,source):
            gui.install()
            config=home/'config.toml';doc=tomlkit.parse(config.read_text('utf-8'))
            doc['mcp_servers']['jev-bridge']['tool_timeout_sec']=40
            doc['mcp_servers']['other']={'command':'leave-me-alone'}
            config.write_text('# User comment\n'+tomlkit.dumps(doc),encoding='utf-8')
            record_file=root/'reports/registration.json';record=json.loads(record_file.read_text('utf-8'))
            record['entry']=doc.unwrap()['mcp_servers']['jev-bridge'];record_file.write_text(json.dumps(record),encoding='utf-8')
            manage.register()
            result=tomlkit.parse(config.read_text('utf-8')).unwrap()
            self.assertEqual(result['mcp_servers']['jev-bridge'],manage.desired())
            self.assertEqual(result['mcp_servers']['other'],{'command':'leave-me-alone'})
            self.assertIn('# User comment',config.read_text('utf-8'))
            self.assertFalse(gui.install()['changed'])

    def test_corrupt_manifest_is_rejected_before_new_install_writes(self):
        with self.sandbox() as (root,home,user,source):
            (home/'jev-integration.json').write_text('{invalid JSON',encoding='utf-8')
            before=(home/'config.toml').read_bytes()
            with self.assertRaises(json.JSONDecodeError):gui.install()
            self.assertEqual((home/'config.toml').read_bytes(),before)
            self.assertFalse((user/'.agents/skills/jev-gui-delegate').exists())
            self.assertFalse((home/'hooks.json').exists())

    def test_bootstrap_reinstall_refreshes_removed_manifest_and_preserves_custom_fields(self):
        with self.sandbox() as (root,home,user,source):
            gui.install()
            official=user/'.agents/skills/typesafe-ai/SKILL.md';official.parent.mkdir(parents=True)
            official.write_text('Existing official skill',encoding='utf-8')
            python=root/'.venv/Scripts/python.exe';python.parent.mkdir(parents=True);python.touch()
            manifest=home/'jev-integration.json';data=json.loads(manifest.read_text('utf-8'))
            data.update(registration='removed',custom_user_setting={'keep':True})
            manifest.write_text(json.dumps(data),encoding='utf-8')
            calls=[]
            def run(command,**kwargs):
                calls.append(command)
                if command[1:]==[str(root/'manage.py'),'register']:manage.register()
                return subprocess.CompletedProcess(command,0)
            with patch.object(bootstrap,'ROOT',root),patch.dict(os.environ,{'CODEX_HOME':str(home)}),patch.object(bootstrap.subprocess,'run',side_effect=run):
                bootstrap.main()
            data=json.loads(manifest.read_text('utf-8'))
            self.assertEqual(data['registration'],'registered')
            self.assertEqual(data['custom_user_setting'],{'keep':True})
            self.assertEqual(data['runtime']['python_executable'],str(python))
            self.assertTrue(any(command[1:]==[str(root/'scripts/setup-runtime.py')] for command in calls))
            self.assertFalse(gui.install()['changed'])

    @unittest.skipUnless(sys.platform=='win32','Windows CMD entry point')
    def test_combined_cmd_stops_when_bootstrap_fails(self):
        with tempfile.TemporaryDirectory(prefix='jev cmd entry ') as folder:
            root=Path(folder)
            shutil.copyfile(Path(__file__).resolve().parents[1]/'install-skill.cmd',root/'install-skill.cmd')
            (root/'install.cmd').write_text('@echo off\nexit /b 7\n',encoding='ascii')
            (root/'gui-install.cmd').write_text('@echo off\necho should-not-run> "%~dp0unexpected.txt"\nexit /b 0\n',encoding='ascii')
            result=subprocess.run(['cmd.exe','/d','/c',str(root/'install-skill.cmd')],cwd=root,capture_output=True)
            self.assertEqual(result.returncode,7,result.stderr.decode(errors='replace'))
            self.assertFalse((root/'unexpected.txt').exists())

if __name__=='__main__':unittest.main()
