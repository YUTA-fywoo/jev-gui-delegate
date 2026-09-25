import asyncio,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gui_delegate.schema import Contract
from gui_delegate.examples import workflow
from gui_delegate.security import Stop
from gui_delegate.clipboard import opened,snapshot_open,paste_with_restore
from gui_delegate.tests.test_guards import FakeDriver,button,cp
from gui_delegate.tests import test_guards as guard_fixtures

class Extensions(unittest.TestCase):
    def test_extra_surface_requires_complete_identity(self):
        c=workflow();c['targets']={'second':{'driver':'browser'}}
        with self.assertRaises(ValueError):Contract.model_validate(c)
    def test_skip_predicate_cannot_reference_other_surface(self):
        c=workflow();c['steps'][0]['optional_if']={'surface':'other','kind':'exists','target':{'role':'button'}}
        with self.assertRaises(ValueError):Contract.model_validate(c)
    def test_clipboard_changed_preserves_new_content_and_recovery(self):
        # Controlled user-copy race: no access to the real clipboard or user state.
        from contextlib import nullcontext
        from unittest.mock import MagicMock
        from gui_delegate import storage
        fake_data=MagicMock();recovery=fake_data.__truediv__.return_value;recovery.exists.return_value=False
        with patch('gui_delegate.clipboard.opened',side_effect=lambda:nullcontext()),patch('gui_delegate.clipboard.snapshot_open',return_value=[(13,b'original')]),patch('gui_delegate.clipboard.put_open') as put,patch('gui_delegate.clipboard.u') as api,patch.object(storage,'DATA',fake_data),patch.object(storage,'save'),patch.object(storage,'protect_directory'):
            api.GetClipboardSequenceNumber.side_effect=[10,11,11]
            with self.assertRaisesRegex(Stop,'USER_CLIPBOARD_CHANGED'):paste_with_restore('synthetic',lambda x:self.fail('must not apply'))
            self.assertEqual(put.call_count,1);recovery.unlink.assert_not_called()
    def test_clipboard_recovery_refuses_newer_clipboard(self):
        from contextlib import nullcontext
        from gui_delegate import storage
        from gui_delegate.clipboard import restore_pending
        from unittest.mock import MagicMock
        fake_data=MagicMock();fake_data.__truediv__.return_value.exists.return_value=True
        with patch('gui_delegate.clipboard.opened',side_effect=lambda:nullcontext()),patch('gui_delegate.clipboard.put_open') as put,patch('gui_delegate.clipboard.u') as api,patch.object(storage,'DATA',fake_data),patch.object(storage,'read',return_value={'phase':'published','sequence':10,'original':[]}):
            api.GetClipboardSequenceNumber.return_value=11
            with self.assertRaisesRegex(Stop,'RECOVERY_NOT_APPLIED_NEW_CLIPBOARD'):restore_pending()
            put.assert_not_called()
    def test_shell_quoted_cua_report_is_not_gui_action(self):
        from gui_delegate.hook import decide
        self.assertEqual(decide({'tool_name':'Bash','tool_input':{'cmd':"print({'input':'await cua.getState();'})"}}),{})
    def test_unknown_surface_rejected(self):
        c=workflow();c['steps'][0]['surface']='invented'
        with self.assertRaises(ValueError):Contract.model_validate(c)
    def test_captured_input_cannot_preseed_values(self):
        c=workflow();c['inputs']['name'].update(captured=True)
        with self.assertRaises(ValueError):Contract.model_validate(c)
    def test_drag_needs_exact_destination(self):
        c=workflow();c['scope']['actions']+=['drag'];c['steps'][0].update(op='drag',destination={'role':'region','semantic':True})
        with self.assertRaises(ValueError):Contract.model_validate(c)
    def test_cross_surface_postcondition_rejected(self):
        c=workflow();c['steps'][0]['after'][0]['surface']='other'
        with self.assertRaises(ValueError):Contract.model_validate(c)
    def test_clipboard_restored_before_driver_exception(self):
        # Exercise the real transaction order against isolated clipboard/storage
        # boundaries; the user's current clipboard format must not affect tests.
        from contextlib import nullcontext
        from unittest.mock import MagicMock
        from gui_delegate import storage
        before=[(13,b'original')]; current=list(before)
        fake_data=MagicMock();recovery=fake_data.__truediv__.return_value;recovery.exists.return_value=False
        def put(values):current[:]=values
        def failure(value):
            self.assertEqual(value,'Synthetic clipboard test')
            self.assertEqual(current,before)
            recovery.unlink.assert_called_once_with(missing_ok=True)
            raise RuntimeError('controlled driver failure')
        with patch('gui_delegate.clipboard.opened',side_effect=lambda:nullcontext()),patch('gui_delegate.clipboard.snapshot_open',side_effect=lambda:list(current)),patch('gui_delegate.clipboard.put_open',side_effect=put) as put_mock,patch('gui_delegate.clipboard.u') as api,patch('gui_delegate.clipboard.k'),patch('gui_delegate.clipboard.c.wstring_at',return_value='Synthetic clipboard test'),patch.object(storage,'DATA',fake_data),patch.object(storage,'save'),patch.object(storage,'protect_directory'):
            api.GetClipboardSequenceNumber.return_value=10
            with self.assertRaisesRegex(RuntimeError,'controlled'):paste_with_restore('Synthetic clipboard test',failure)
            self.assertEqual(current,before)
            self.assertEqual(put_mock.call_count,2)
    def test_clipboard_busy_no_mutation(self):
        # Fault injection at the boundary; cannot touch user clipboard through this mock.
        with patch('gui_delegate.clipboard.opened',side_effect=Stop('CLIPBOARD_BUSY')):
            with self.assertRaisesRegex(Stop,'CLIPBOARD_BUSY'):paste_with_restore('test',lambda x:None)
    def test_clipboard_secrets_rejected_before_access(self):
        with patch('gui_delegate.clipboard.opened') as access:
            with self.assertRaisesRegex(Stop,'SENSITIVE_INPUT'):paste_with_restore('password=synthetic',lambda x:None)
            access.assert_not_called()
    def test_cli_invalid_values_not_echoed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'request.json';path.write_text(json.dumps({'goal':'TEST_SECRET_CANARY','code':'TEST_SECRET_CANARY'}),'utf-8')
            p=subprocess.run([sys.executable,'-m','gui_delegate.cli','run',str(path)],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0);self.assertNotIn('TEST_SECRET_CANARY',p.stdout+p.stderr)
    def test_captured_secret_cannot_be_exported(self):
        c=workflow();c['scope']['actions'].append('copy');c['inputs']['captured']={'value':'','captured':True}
        c['steps']=[{'id':'copy','intent':'Copy current value','op':'copy','target':{'role':'button','name':'Save locally'},'output_ref':'captured','after':[{'kind':'exists','target':{'role':'button','name':'Save locally'}}]}]
        d=FakeDriver([button().model_copy(update={'value':'password=synthetic'})]);ctl=guard_fixtures.Guards().setup_controller(d,Contract.model_validate(c))
        with self.assertRaisesRegex(Stop,'CAPTURED_VALUE_NOT_SAFE'):ctl.perform(ctl.contract.steps[0],cp())
        self.assertEqual(d.actions,0);self.assertEqual(ctl.artifacts,{})

if __name__=='__main__':unittest.main()
