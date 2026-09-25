import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from gui_delegate.hook import decide,gateway_call,bind,code_hash
from gui_delegate.fallback_policy import issue,valid_grant,routing
from gui_delegate.schema import Contract
from gui_delegate.examples import workflow
from gui_delegate.security import Stop

PREFIX='await jevStrictGateway.dispatch({browser:chromeConnection,request:'
def gateway(request):return PREFIX+json.dumps(request)+'},nodeRepl);'

class StrictRouting(unittest.TestCase):
    def setUp(self):
        legacy=patch('gui_delegate.routing_policy.preference_only',return_value=False)
        legacy.start();self.addCleanup(legacy.stop)
    def decision(self,code):return decide({'tool_name':'mcp__cua_repl__js','tool_input':{'code':code}})
    def test_dedicated_gui_tool_denies_aliases_and_reads(self):
        for code in ['await t.goto("https://example.org")','await t.playwright.domSnapshot()',
                     'await x.content.export({})','await t.clipboard.writeText("hello")',
                     'await t.close()','await t["click"](1)','nodeRepl.write("probe")',
                     'await arbitraryAlias()']:
            with self.subTest(code=code):self.assertEqual(self.decision(code)['hookSpecificOutput']['permissionDecision'],'deny')
    def test_gateway_allowed_without_general_code_escape(self):
        code=gateway({'operation':'run_task','contract_path':'C:/synthetic/contract.json'})
        self.assertEqual(self.decision(code),{})
        for bad in [code+'await t.close();',code.replace('chromeConnection','getBrowser()'),
                    code.replace('"C:/synthetic/contract.json"','getPath()'),
                    code.replace('jevStrictGateway','arbitraryGateway'),
                    gateway({'operation':'eval','arguments':{}}),
                    gateway({'operation':'run_task','contract_path':'x','code':'bad'}),
                    PREFIX+'{"operation":"run_task","contract_path":"x"},other:doSomething()},nodeRepl);']:
            self.assertFalse(gateway_call(bad))
    def test_every_public_task_operation_has_canonical_entry(self):
        for operation in ['resume_task','cancel_task','diagnose_task','close_created_tab']:
            self.assertEqual(self.decision(gateway({'operation':operation,'arguments':{'resume_token':'a'*64}})),{})
    def test_setup_cannot_import_other_module_or_append_code(self):
        setup='let jevStrictGateway = await import("file:///C:/jev/jev-bridge/gui_delegate/chrome_gateway.mjs?release=0.4.1");'
        self.assertEqual(self.decision(setup),{})
        for code in [setup+'await t.close();',setup.replace('chrome_gateway.mjs','chrome_delegate.mjs'),setup.replace('jevStrictGateway','arbitraryName')]:
            self.assertEqual(self.decision(code)['hookSpecificOutput']['permissionDecision'],'deny')
    def test_temporary_errors_and_decision_repairs_do_not_grant_takeover(self):
        c=Contract.model_validate(workflow())
        with tempfile.TemporaryDirectory() as tmp,patch('gui_delegate.fallback_policy.storage.event'):
            directory=Path(tmp)
            for reason in ['LOW_CONFIDENCE','NO_MATCH','JEV_RATE_LIMITED','JEV_NETWORK_ERROR',
                           'JEV_ASK_ASTRA','STATE_KEEPS_CHANGING','INPUT_TEXT_REQUIRED',
                           'CHROME_DRIVER_ERROR','CHROME_CODEX_SESSION_REQUIRED','PROGRAM_DENIED','CANCELLED']:
                (directory/'fallback.dpapi').write_bytes(b'old')
                self.assertFalse(issue(directory,c,reason,time.time()+180))
                self.assertFalse((directory/'fallback.dpapi').exists())
                self.assertFalse(routing({},reason)['direct_astra_gui_allowed'])
    def test_old_broad_grants_cannot_bind(self):
        with patch('gui_delegate.hook.storage.task_directory',return_value=Path('unused')),patch('gui_delegate.hook.storage.read',return_value={'reason':'LOW_CONFIDENCE'}):
            with self.assertRaisesRegex(Stop,'FALLBACK_GRANT_INVALID'):bind('a'*64,'session','mcp__cua_repl__js',{'code':'// jev-fallback:'+'a'*64})
    def test_real_gap_is_scope_and_call_bound_once(self):
        c=Contract.model_validate(workflow());stored={};token='a'*64;tool='mcp__cua_repl__js'
        arguments={'code':'// jev-fallback:'+token+'\nnodeRepl.write("controlled fallback probe");'}
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            def save(p,v):stored[p.name]=dict(v)
            with patch('gui_delegate.fallback_policy.storage.save',side_effect=save),patch('gui_delegate.fallback_policy.storage.event'):
                self.assertTrue(issue(directory,c,'CHROME_JS_DIALOG_HOST_BLOCKED',time.time()+180))
            self.assertTrue(valid_grant(stored['fallback.dpapi']))
            stored['result.dpapi']={'status':'escalated','escalation_reason':'CHROME_JS_DIALOG_HOST_BLOCKED'}
            self.assertEqual(stored['fallback.dpapi']['scope'],c.scope.model_dump())
            with patch('gui_delegate.hook.storage.task_directory',return_value=directory),patch('gui_delegate.hook.storage.read',side_effect=lambda p:dict(stored[p.name])),patch('gui_delegate.hook.storage.save',side_effect=save),patch('gui_delegate.hook.storage.event'):
                bind(token,'session',tool,arguments)
                for event in [{'session_id':'other','tool_name':tool,'tool_input':arguments},
                              {'session_id':'session','tool_name':tool,'tool_input':{'code':arguments['code']+'extra'}}]:
                    self.assertEqual(decide(event)['hookSpecificOutput']['permissionDecision'],'deny')
                event={'session_id':'session','tool_name':tool,'tool_input':arguments}
                self.assertEqual(decide(event),{})
                self.assertEqual(decide(event)['hookSpecificOutput']['permissionDecision'],'deny')
                stored['result.dpapi']['status']='cancelled'
                with self.assertRaisesRegex(Stop,'FALLBACK_GRANT_INVALID'):bind(token,'session',tool,arguments)
    def test_zero_model_calls_are_reported_honestly(self):
        self.assertEqual(routing({'actions':12,'jev_requests':0})['model_participation'],'no_jev_request')
        self.assertEqual(routing({'jev_requests':1})['model_participation'],'jev_called')

if __name__=='__main__':unittest.main()
