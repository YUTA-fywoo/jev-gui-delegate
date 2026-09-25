import unittest
from unittest.mock import patch
import pywintypes
from gui_delegate.drivers import Windows
from gui_delegate.security import Stop

class WindowsSnapshotTests(unittest.TestCase):
    def test_destroyed_child_discards_snapshot_without_replaying_action(self):
        driver=Windows(None);result=object()
        with patch.object(driver,'_observe',side_effect=[pywintypes.error(1400,'GetWindowText','synthetic destroyed child'),result]) as observe,patch.object(driver,'act') as act:
            self.assertIs(driver.observe(),result);self.assertEqual(observe.call_count,2);act.assert_not_called()
    def test_reobservation_is_finite(self):
        driver=Windows(None)
        with patch.object(driver,'_observe',side_effect=pywintypes.error(1400,'GetWindowText','synthetic destroyed child')) as observe:
            with self.assertRaisesRegex(Stop,'STATE_KEEPS_CHANGING'):driver.observe()
            self.assertEqual(observe.call_count,3)
    def test_other_native_error_is_not_hidden_or_retried(self):
        driver=Windows(None)
        with patch.object(driver,'_observe',side_effect=pywintypes.error(5,'GetWindowText','synthetic access denied')) as observe:
            with self.assertRaises(pywintypes.error):driver.observe()
            self.assertEqual(observe.call_count,1)
