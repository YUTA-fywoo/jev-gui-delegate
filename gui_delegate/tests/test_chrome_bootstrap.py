import unittest
from gui_delegate.chrome_bootstrap import prepare_environment

class BootstrapTests(unittest.TestCase):
    def test_inherited_credential_preserved_without_loading_saved_secrets(self):
        current={'TYPESAFE_API_KEY':'synthetic-inherited-key','PATH':'host-path'}
        source={'TYPESAFE_API_KEY':'saved-secret-must-not-be-used','PATH':'saved-path','SYSTEMROOT':'synthetic-system','UNRELATED':'not-forwarded'}
        prepare_environment(source,current)
        self.assertEqual(current,{'TYPESAFE_API_KEY':'synthetic-inherited-key','PATH':'host-path','SYSTEMROOT':'synthetic-system','PYTHONUTF8':'1'})
        empty={};prepare_environment(source,empty)
        self.assertNotIn('TYPESAFE_API_KEY',empty)
        self.assertNotIn('UNRELATED',empty)

if __name__=='__main__':unittest.main()
