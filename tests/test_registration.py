import contextlib
import io
import json
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import manage
from jev_client import ROOT
import tomlkit

class RegistrationTests(unittest.TestCase):
    def test_idempotent_and_scoped_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/"project";root.mkdir();(root/"reports").mkdir()
            home=Path(temporary)/"codex";home.mkdir()
            path=home/"config.toml"
            original='# preserve comment\nmodel = "gpt-6-astra"\n[features]\nsomething = true\n[mcp_servers.other]\ncommand = "existing"\n'
            path.write_text(original,encoding="utf-8")
            with patch.object(manage,"ROOT",root),patch.object(manage,"codex_home",lambda:home),contextlib.redirect_stdout(io.StringIO()):
                manage.register();first=path.read_bytes();manage.register()
                self.assertEqual(path.read_bytes(),first)
                report=json.loads((root/"reports/registration.json").read_text("utf-8"))
                self.assertEqual(Path(report["backup"]).read_text("utf-8"),original)
                doc=tomlkit.parse(path.read_text("utf-8"));doc["new_unrelated_setting"]=42
                path.write_text(tomlkit.dumps(doc),encoding="utf-8")
                manage.rollback()
                result=tomlkit.parse(path.read_text("utf-8")).unwrap()
                expected=tomlkit.parse(original).unwrap();expected["new_unrelated_setting"]=42
                self.assertEqual(result,expected)
                self.assertIn('# preserve comment',path.read_text("utf-8"))

    def test_name_collision_preserves_existing(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary);path=home/"config.toml"
            original='[mcp_servers.jev-bridge]\ncommand = "someone-elses-tool"\n'
            path.write_text(original,encoding="utf-8")
            with patch.object(manage,"codex_home",lambda:home):
                with self.assertRaises(RuntimeError):manage.register()
            self.assertEqual(path.read_text("utf-8"),original)

if __name__=="__main__":
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RegistrationTests))
    (ROOT/"reports/registration-tests.json").write_text(json.dumps({"status":"PASS" if result.wasSuccessful() else "FAIL","tests_run":result.testsRun},indent=2),encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
