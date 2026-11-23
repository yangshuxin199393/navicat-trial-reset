"""以合成文件验证周期与文件边界，不访问真实Navicat配置。"""
import tempfile
import time
import unittest
import io
import json
from pathlib import Path
from unittest.mock import patch

import Run as timer


class TimerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.store = self.root / 'store'
        self.data = self.root / 'data'
        self.pref = self.root / 'preferences.plist'
        self.store.mkdir()
        self.data.mkdir()
        self.now = int(time.time())
        self.stamp = self.store / 'last-success'
        self.stamp.write_text(str(self.now - timer.DEFAULT_INTERVAL_DAYS * timer.SECONDS_PER_DAY - 1))
        self.pref.write_text('synthetic preferences')
        self.marker = self.data / ('.' + 'A' * 32)
        self.marker.write_text('synthetic marker')
        self.connections = self.data / 'Connections'
        self.connections.write_text('synthetic connections')
        self.addCleanup(patch.stopall)
        patch.multiple(timer, STORE=self.store, DATA=self.data, PREF=self.pref).start()
        patch.object(timer.sys, 'argv', ['Run.py']).start()

    def test_not_due_has_no_side_effects(self):
        self.stamp.write_text(str(self.now))
        with patch.object(timer, 'app_running', side_effect=AssertionError('not due')):
            self.assertEqual(timer.main(), 0)
        self.assertTrue(self.pref.exists())
        self.assertFalse((self.store / 'reset-backups').exists())

    def test_running_application_defers(self):
        before = self.stamp.read_text()
        with patch.object(timer, 'app_running', return_value=True):
            self.assertEqual(timer.main(), 0)
        self.assertTrue(self.pref.exists())
        self.assertTrue(self.marker.exists())
        self.assertEqual(self.stamp.read_text(), before)

    def test_due_moves_only_targets_and_keeps_restorable_backup(self):
        unrelated = self.data / ('.' + 'b' * 32)
        unrelated.write_text('outside uppercase allowlist')
        with patch.object(timer, 'app_running', return_value=False):
            self.assertEqual(timer.main(), 0)
        backup = next((self.store / 'reset-backups').iterdir())
        self.assertEqual((backup / self.pref.name).read_text(), 'synthetic preferences')
        self.assertEqual((backup / self.marker.name).read_text(), 'synthetic marker')
        self.assertFalse(self.pref.exists())
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.connections.read_text(), 'synthetic connections')
        self.assertTrue(unrelated.exists())
        self.assertGreaterEqual(int(self.stamp.read_text()), self.now)

    def test_symlink_is_rejected_before_mutation(self):
        self.pref.unlink()
        self.pref.symlink_to(self.connections)
        before = self.stamp.read_text()
        with self.assertRaises(RuntimeError):
            timer.reset_files(self.now)
        self.assertTrue(self.marker.exists())
        self.assertEqual(self.stamp.read_text(), before)

    def test_failed_move_does_not_advance_timestamp(self):
        before = self.stamp.read_text()
        with patch.object(timer, 'app_running', return_value=False), \
                patch.object(Path, 'rename', side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError):
                timer.main()
        self.assertEqual(self.stamp.read_text(), before)
        self.assertTrue(self.pref.exists())

    def test_status_does_not_reset_due_files(self):
        with patch.object(timer.sys, 'argv', ['Run.py', '--status']), \
                patch.object(timer, 'app_running', return_value=False):
            self.assertEqual(timer.main(), 0)
        self.assertTrue(self.pref.exists())
        self.assertTrue(self.marker.exists())

    def test_configured_interval_controls_due_time_and_status(self):
        (self.store / 'config.json').write_text('{"interval_days": 30}')
        out = io.StringIO()
        with patch.object(timer.sys, 'argv', ['Run.py', '--status']), \
                patch.object(timer, 'app_running', return_value=False), patch('sys.stdout', out):
            self.assertEqual(timer.main(), 0)
        status = json.loads(out.getvalue())
        self.assertEqual(status['interval_days'], 30)
        self.assertFalse(status['due'])
        with patch.object(timer, 'app_running', side_effect=AssertionError('not due')):
            self.assertEqual(timer.main(), 0)
        self.assertTrue(self.pref.exists())

    def test_shorter_interval_is_used_for_processing_and_next_due(self):
        (self.store / 'config.json').write_text('{"interval_days": 2}')
        out = io.StringIO()
        with patch.object(timer, 'app_running', return_value=False), patch('sys.stdout', out):
            self.assertEqual(timer.main(), 0)
        next_due = timer.datetime.fromtimestamp(int(self.stamp.read_text()) + 2 * timer.SECONDS_PER_DAY)
        self.assertIn(next_due.astimezone().isoformat(timespec='seconds'), out.getvalue())
        self.assertFalse(self.pref.exists())

    def test_invalid_configuration_stops_before_file_processing(self):
        invalid = ['invalid json', '[]', '{}', '{"interval_days":13,"typo":1}']
        invalid += [json.dumps({'interval_days': value}) for value in (0, -1, 366, True, None, 1.5, '13')]
        before = self.stamp.read_text()
        for config in invalid:
            with self.subTest(config=config):
                (self.store / 'config.json').write_text(config)
                with patch.object(timer, 'app_running', side_effect=AssertionError('invalid config')):
                    with self.assertRaises(ValueError):
                        timer.main()
                self.assertTrue(self.pref.exists())
                self.assertTrue(self.marker.exists())
                self.assertEqual(self.stamp.read_text(), before)

    def test_configuration_bounds_and_legacy_default(self):
        self.assertEqual(timer.read_interval_days(), 13)
        for days in (1, 365):
            with self.subTest(days=days):
                (self.store / 'config.json').write_text(json.dumps({'interval_days': days}))
                self.assertEqual(timer.read_interval_days(), days)


if __name__ == '__main__':
    unittest.main()
