"""Exercise actual Windows credential storage with an isolated synthetic entry."""
import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import credentials
from jev_client import ROOT

class CredentialTests(unittest.TestCase):
    def test_windows_roundtrip_and_removal(self):
        target="Codex/jev-bridge/self-test/"+uuid.uuid4().hex
        with patch.object(credentials,"TARGET",target),patch.dict(os.environ,{"TYPESAFE_API_KEY":""}):
            try:
                self.assertEqual(credentials.resolve_key(),(None,"missing"))
                credentials.save_key("synthetic-roundtrip-only")
                value,source=credentials.resolve_key()
                self.assertEqual(value,"synthetic-roundtrip-only")
                self.assertEqual(source,"windows-credential-manager")
            finally:
                credentials.remove_key()
            self.assertEqual(credentials.resolve_key(),(None,"missing"))

if __name__=="__main__":
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CredentialTests))
    (ROOT/"reports/credential-tests.json").write_text(json.dumps({"status":"PASS" if result.wasSuccessful() else "FAIL","tests_run":result.testsRun,"synthetic_only":True},indent=2),encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
