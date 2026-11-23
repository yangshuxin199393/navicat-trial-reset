"""模拟launchctl验证安装及卸载，不加载真实系统任务。"""
import subprocess
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import install


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.store = self.root / 'store'
        self.agent = self.root / 'agents/test.plist'
        self.addCleanup(patch.stopall)
        patch.multiple(install, STORE=self.store, AGENT=self.agent).start()
        self.calls = patch.object(install.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)).start()

    def test_install_and_update_keep_existing_timestamp(self):
        with patch('sys.argv', ['install.py']):
            install.main()
            before = (self.store / 'last-success').read_text()
            install.main()
        self.assertTrue(self.agent.exists())
        self.assertEqual((self.store / 'last-success').read_text(), before)
        self.assertTrue((self.store / 'task-backups').exists())
        self.assertTrue((self.store / 'Run.py').exists())
        self.assertTrue(any('bootstrap' in args.args[0] for args in self.calls.call_args_list))

    def test_uninstall_keeps_data(self):
        self.store.mkdir()
        (self.store / 'last-success').write_text('123')
        self.agent.parent.mkdir()
        self.agent.write_text('synthetic task')
        with patch('sys.argv', ['install.py', '--uninstall']):
            install.main()
        self.assertFalse(self.agent.exists())
        self.assertEqual((self.store / 'last-success').read_text(), '123')

    def test_custom_interval_survives_reinstall_and_can_be_changed(self):
        with patch('sys.argv', ['install.py', '--interval-days', '7']):
            install.main()
        stamp = (self.store / 'last-success').read_text()
        with patch('sys.argv', ['install.py']):
            install.main()
        self.assertEqual(json.loads((self.store / 'config.json').read_text())['interval_days'], 7)
        with patch('sys.argv', ['install.py', '--interval-days', '20']):
            install.main()
        self.assertEqual(json.loads((self.store / 'config.json').read_text())['interval_days'], 20)
        self.assertEqual((self.store / 'last-success').read_text(), stamp)

    def test_invalid_interval_is_rejected_before_launchctl(self):
        for value in ('0', '-1', '366', '1.5', 'abc'):
            with self.subTest(value=value), patch('sys.argv', ['install.py', '--interval-days', value]):
                with self.assertRaises(SystemExit):
                    install.main()
        self.calls.assert_not_called()
        self.assertFalse(self.store.exists())
