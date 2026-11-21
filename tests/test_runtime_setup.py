import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from desktop.runtime_setup import ensure_runtime,requirements_key


class RuntimeSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'project';self.directory=Path(self.temp.name)/'runtime'
        for name in ('desktop','analysis'):(self.root/name).mkdir(parents=True)
        (self.root/'desktop/requirements.txt').write_text('numpy==2.5.5\n');(self.root/'analysis/requirements.txt').write_text('matplotlib==3.11.2\n');(self.directory/'bin').mkdir(parents=True);(self.directory/'bin/python').touch()
    def test_healthy_cached_runtime_skips_package_installation(self):
        (self.directory/'ready.json').write_text(json.dumps(dict(requirements_sha256=requirements_key(self.root))))
        with patch('desktop.runtime_setup.probe',return_value=True),patch('desktop.runtime_setup.subprocess.run') as install:
            self.assertEqual(ensure_runtime(self.root,self.directory),self.directory/'bin/python');install.assert_not_called()
        before=requirements_key(self.root);(self.root/'analysis/requirements.txt').write_text('matplotlib==3.11.3\n');self.assertNotEqual(before,requirements_key(self.root))
    def test_missing_plugins_force_repair_before_marking_ready(self):
        (self.directory/'ready.json').write_text(json.dumps(dict(requirements_sha256=requirements_key(self.root))))
        with patch('desktop.runtime_setup.probe',side_effect=[False,True]),patch('desktop.runtime_setup.subprocess.run') as install:ensure_runtime(self.root,self.directory)
        self.assertIn('--force-reinstall',install.call_args.args[0]);self.assertEqual(json.loads((self.directory/'ready.json').read_text())['requirements_sha256'],requirements_key(self.root))
    def test_failed_install_never_creates_ready_marker(self):
        with patch('desktop.runtime_setup.subprocess.run',side_effect=subprocess.CalledProcessError(1,['pip'])):
            with self.assertRaises(subprocess.CalledProcessError):ensure_runtime(self.root,self.directory)
        self.assertFalse((self.directory/'ready.json').exists())


if __name__=='__main__':unittest.main()
