"""Controlled retained native and official Chrome ownership regressions."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from gui_delegate.examples import workflow
from gui_delegate.schema import Contract
from gui_delegate.security import Stop
from gui_delegate.input_guard import InputGuard,mode_for
from gui_delegate.drivers import create_driver,Windows

def chrome():return Contract.model_validate(workflow())
def native():
    c=workflow();c['target']={'driver':'windows','hwnd':1,'process_id':1,'executable':'C:/synthetic.exe','window_title':'Synthetic'}
    return Contract.model_validate(c)
class InputOwnershipTests(unittest.TestCase):
    def test_official_paste_does_not_access_os_input_or_clipboard(self):
        c=chrome();c.steps[0].op='paste'
        with patch('gui_delegate.input_guard.last_input_tick',side_effect=AssertionError('OS input queried')):
            g=InputGuard(c);g.start();g.check();g.release();g.close()
        self.assertEqual(g.mode,'official_browser_session')
    def test_native_guard_pauses_and_requires_explicit_release(self):
        with patch('gui_delegate.input_guard.last_input_tick',return_value=10):g=InputGuard(native());g.check()
        with patch('gui_delegate.input_guard.last_input_tick',return_value=11):
            for _ in range(2):
                with self.assertRaisesRegex(Stop,'USER_TAKEOVER'):g.check()
            g.release();g.check()
    def test_native_named_surface_keeps_session_guard(self):
        c=chrome();c.targets['native']=native().target
        self.assertEqual(mode_for(c),'session')
    def test_removed_driver_never_launches_subprocess(self):
        c=chrome();c.target.connection='isolated';c.target.tab_id=None
        with patch('subprocess.Popen',side_effect=AssertionError('Must not launch')):
            with self.assertRaisesRegex(Stop,'LEGACY_BROWSER_RETIRED_USE_OFFICIAL_CHROME'):create_driver(c)
    def test_removed_named_target_is_rejected_before_opening_native(self):
        c=native();target=chrome().target;target.connection='isolated';target.tab_id=None;c.targets['old']=target
        with patch.object(Windows,'open',side_effect=AssertionError('No partial actions')):
            with self.assertRaisesRegex(Stop,'LEGACY_BROWSER_RETIRED_USE_OFFICIAL_CHROME'):create_driver(c)
    def test_official_session_and_mixed_target_boundary(self):
        c=chrome()
        with self.assertRaisesRegex(Stop,'CHROME_CODEX_SESSION_REQUIRED'):create_driver(c)
        c.targets['native']=native().target
        with self.assertRaisesRegex(Stop,'CHROME_MIXED_DESKTOP_REQUIRES_SEPARATE_TASK'):create_driver(c,browser_session=SimpleNamespace())
if __name__=='__main__':unittest.main()
