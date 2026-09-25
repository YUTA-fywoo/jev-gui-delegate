import queue, unittest
from types import SimpleNamespace
from unittest.mock import patch
from gui_delegate.schema import Contract
from gui_delegate.chrome_session import ChromeSessionDriver,StdioBrowserSession
from gui_delegate.tests.chrome_contract import contract
from gui_delegate.security import Stop,validate_contract

class ChromeSessionTests(unittest.TestCase):
    def data(self):return contract('http://127.0.0.1:5000/workflow','known-tab')
    def test_requires_explicit_tab_identity(self):
        c=self.data();c['target'].pop('tab_id')
        with self.assertRaises(ValueError):Contract.model_validate(c)
    def test_cannot_use_personal_connection_as_native_target(self):
        c=self.data();c['target']['driver']='windows'
        with self.assertRaises(ValueError):Contract.model_validate(c)
    def test_unauthorized_origin_rejected_before_session(self):
        c=self.data();c['target']['url']='https://unauthorized.example/'
        with self.assertRaisesRegex(Stop,'ORIGIN_DENIED'):validate_contract(Contract.model_validate(c))
    def test_no_browser_session_never_falls_back_to_other_browser(self):
        from gui_delegate.drivers import create_driver
        with self.assertRaisesRegex(Stop,'CHROME_CODEX_SESSION_REQUIRED'):create_driver(Contract.model_validate(self.data()))
    def test_unsupported_action_stops_before_touching_browser(self):
        c=Contract.model_validate(self.data());c.steps[0].op='unsupported';calls=[]
        d=ChromeSessionDriver(c,SimpleNamespace(exchange=lambda *a:calls.append(a)))
        with self.assertRaisesRegex(Stop,'CHROME_UNSUPPORTED_ACTION'):d.open()
        self.assertEqual(calls,[])
    def test_response_id_mismatch_rejected(self):
        session=StdioBrowserSession.__new__(StdioBrowserSession);session.serial=0;session.queue=queue.Queue();session.emit=lambda x:None
        session.queue.put({'id':99,'ok':True,'value':{}})
        with self.assertRaisesRegex(Stop,'CHROME_PROTOCOL_INVALID'):session.exchange('observe',{})
    def test_remote_error_never_returns_arbitrary_page_text(self):
        session=StdioBrowserSession.__new__(StdioBrowserSession);session.serial=0;session.queue=queue.Queue();session.emit=lambda x:None
        session.queue.put({'id':1,'ok':False,'error':'synthetic untrusted secret text'})
        with self.assertRaisesRegex(Stop,'CHROME_DRIVER_ERROR'):session.exchange('observe',{})
    def test_interruption_resume_requires_user_release(self):
        import asyncio
        from pathlib import Path
        from gui_delegate.service import resume_task
        with patch('gui_delegate.service.storage.task_directory',return_value=Path('unused')),patch('gui_delegate.service.storage.read',return_value={'status':'paused','escalation_reason':'CHROME_SESSION_INTERRUPTED'}):
            with self.assertRaisesRegex(Stop,'USER_RELEASE_REQUIRED'):asyncio.run(resume_task({'resume_token':'a'*64,'continue_task':True}))
    @patch('gui_delegate.routing_policy.preference_only',return_value=False)
    def test_discovery_exception_cannot_carry_actions(self,_legacy):
        from gui_delegate.hook import decide
        for code in ['await cua.getState();','await cua.rewriteDocumentation();','let chrome = await cua.getBrowser({id:"2"});']:
            self.assertEqual(decide({'tool_name':'mcp__cua_repl__js','tool_input':{'code':code}}),{})
        for code in ['await cua.getState(); await tab.click(1);','await cua.rewriteDocumentation(); await tab.fill("bad");','await cua.getState({code:doSomething()});','await cua.getBrowser({id:computeId()});']:
            self.assertEqual(decide({'tool_name':'mcp__cua_repl__js','tool_input':{'code':code}})['hookSpecificOutput']['permissionDecision'],'deny')
    def test_checkpoint_segment_and_reset(self):
        session=StdioBrowserSession.__new__(StdioBrowserSession);session.started=0
        with patch('gui_delegate.chrome_session.time.monotonic',return_value=36):
            with self.assertRaisesRegex(Stop,'CHROME_SEGMENT_COMPLETE'):session.check_segment()
            session.reset_segment();session.check_segment()
    def test_disabled_route_blocks_new_task(self):
        from gui_delegate.chrome_policy import require_enabled
        with patch('gui_delegate.chrome_policy.describe',return_value={'enabled':False}):
            with self.assertRaisesRegex(Stop,'CHROME_ROUTE_DISABLED'):require_enabled()

if __name__=='__main__':unittest.main()
