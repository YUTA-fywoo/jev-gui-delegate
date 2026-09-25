"""Behavior checks for the active non-blocking Jev-first route."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from gui_delegate import routing_policy
from gui_delegate.fallback_policy import routing
from gui_delegate.hook import decide


class PreferredRouting(unittest.TestCase):
    def setUp(self):
        pref = patch('gui_delegate.routing_policy.preference_only', return_value=True)
        pref.start()
        self.addCleanup(pref.stop)

    def test_supported_gui_surfaces_need_no_grant(self):
        for tool, code in [('mcp__cua_repl__js', 'await tab.getAXState();'),
                           ('mcp__cua_repl__js', 'await tab.click(1);'),
                           ('mcp__node_repl__js', 'await import("@oai/sky");'),
                           ('Bash', 'import pywinauto')]:
            with self.subTest(tool=tool, code=code):
                self.assertEqual(decide({'tool_name': tool, 'tool_input': {'code': code}}), {})

    def test_recoverable_errors_do_not_redirect_gui_to_astra(self):
        for reason in ['LOW_CONFIDENCE', 'NO_MATCH', 'INPUT_TEXT_REQUIRED',
                       'LOCAL_RUNTIME_FAILURE', 'JEV_NETWORK_ERROR',
                       'CHROME_STATE_TOO_LARGE', 'CHROME_FRAME_DEPTH_LIMIT',
                       'OBSERVATION_TOO_LARGE_USE_SCOPED_ADAPTER']:
            with self.subTest(reason=reason):
                result = routing({}, reason)
                self.assertFalse(result['direct_astra_gui_allowed'])
                self.assertFalse(result['fallback_grant_required'])
                self.assertEqual(result['model_participation'], 'no_jev_request')
                self.assertEqual(result['recovery'], 'repair_or_supply_minimal_input_then_resume_jev')

    def test_actual_adapter_gap_allows_scoped_takeover_without_grant(self):
        for reason in ['OPERATION_UNSUPPORTED', 'CHROME_FRAME_COORDINATES_REQUIRE_ASTRA',
                       'CHROME_JS_DIALOG_HOST_BLOCKED', 'UIA_RANGE_PATTERN_UNAVAILABLE']:
            with self.subTest(reason=reason):
                result = routing({'jev_requests': 1}, reason)
                self.assertTrue(result['direct_astra_gui_allowed'])
                self.assertFalse(result['fallback_grant_required'])
                self.assertEqual(result['model_participation'], 'jev_called')
                self.assertEqual(result['recovery'], 'astra_only_for_unsupported_portion_then_jev')

    def test_success_and_segment_end_do_not_request_astra_gui(self):
        self.assertFalse(routing({})['direct_astra_gui_allowed'])
        self.assertIsNone(routing({})['recovery'])
        result = routing({}, 'CHROME_SEGMENT_COMPLETE')
        self.assertFalse(result['direct_astra_gui_allowed'])
        self.assertEqual(result['recovery'], 'continue_same_executor_task')

    def test_stops_and_permissions_are_not_takeover_instructions(self):
        for reason in ['USER_TAKEOVER', 'USER_CLIPBOARD_CHANGED', 'CANCELLED',
                       'CHROME_SESSION_INTERRUPTED', 'EMERGENCY_STOP_ACTIVE', 'ACCESS_DENIED']:
            with self.subTest(reason=reason):
                self.assertFalse(routing({}, reason)['direct_astra_gui_allowed'])

    def test_malformed_route_config_stays_advisory(self):
        with patch.object(routing_policy.POLICY_PATH.__class__, 'read_text', return_value='{broken'):
            # Call the original function, bypassing the setUp patch for this check.
            import importlib.util
            spec = importlib.util.spec_from_file_location('routing_config_probe', routing_policy.__file__)
            probe = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(probe)
            self.assertTrue(probe.preference_only())

    def test_real_hook_process_uses_installed_preference(self):
        hook = Path(__file__).resolve().parents[1] / 'hook.py'
        event = {'tool_name': 'mcp__cua_repl__js', 'session_id': 'preferred-routing-test',
                 'tool_input': {'code': 'await tab.getAXState();'}}
        result = subprocess.run([sys.executable, str(hook)], input=json.dumps(event),
                                text=True, capture_output=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout), {})


if __name__ == '__main__':
    unittest.main()
