"""Data round trips, invalid records and synchronized native-viewer state."""
from pathlib import Path
import os
import stat
import sys
import tempfile
import time
import unittest

from desktop.run_data import DEFAULTS, ROOT, decode_run, load_run, run_experiment, save_run, validate_parameters
from desktop.qt_compat import prepare_platform_plugins

BASELINE = ROOT/"results/phase1/baseline"


class RunDataTest(unittest.TestCase):
    def test_default_parameters(self):
        p = validate_parameters(DEFAULTS)
        self.assertEqual(p["steps"],600)
        self.assertEqual((p["source"],p["sink"],p["initial_conductivity"]),(0,3,.5))

    @unittest.skipUnless(sys.platform=="darwin","macOS file flags")
    def test_hidden_platform_plugin_can_be_discovered(self):
        with tempfile.TemporaryDirectory() as temporary:
            plugin = Path(temporary)/"example.dylib"
            plugin.write_bytes(b"test fixture")
            original = plugin.stat().st_flags
            os.chflags(plugin,original | stat.UF_HIDDEN)
            prepare_platform_plugins(temporary)
            self.assertEqual(plugin.stat().st_flags,original & ~stat.UF_HIDDEN)

    def test_invalid_parameters(self):
        for payload in [None,{}, {**DEFAULTS,"source":1}, {**DEFAULTS,"gamma":float("nan")},
                        {**DEFAULTS,"current":True}, {**DEFAULTS,"duration":0},
                        {**DEFAULTS,"dt":.07}, {**DEFAULTS,"gamma":"1.8"}]:
            with self.subTest(payload=payload),self.assertRaises(ValueError):
                validate_parameters(payload)

    def test_recorded_analytic_state(self):
        data = load_run(BASELINE)
        self.assertEqual(len(data.frames),601)
        self.assertEqual(data.frames[0]["d"],[.5]*4)
        for actual,expected in zip(data.frames[0]["q"],[4/3,4/3,2/3,2/3]):
            self.assertAlmostEqual(actual,expected,places=12)
        for actual,expected in zip(data.frames[0]["p"],[16/3,8/3,8/3,0]):
            self.assertAlmostEqual(actual,expected,places=12)
        self.assertEqual(data.frames[-1]["time"],30)

    def test_save_load_preserves_original_bytes(self):
        data = load_run(BASELINE)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"roundtrip.zip"
            save_run(data,path)
            restored = load_run(path)
        self.assertEqual(restored.files,data.files)
        self.assertEqual(restored.frames,data.frames)
        self.assertEqual(restored.parameters,data.parameters)

    def test_truncated_history_rejected(self):
        data = load_run(BASELINE)
        files = dict(data.files)
        files["history.csv"] = files["history.csv"].rsplit(b"\n",2)[0]+b"\n"
        with self.assertRaisesRegex(ValueError,"row count"):
            decode_run(files,"invalid")

    def test_nonfinite_and_reordered_history_rejected(self):
        data = load_run(BASELINE)
        for replacement in (b"nan",b"-0.5"):
            files = dict(data.files)
            files["history.csv"] = files["history.csv"].replace(b",0,0.5,",b",0,"+replacement+b",",1)
            with self.subTest(replacement=replacement),self.assertRaises(ValueError):
                decode_run(files,"invalid")
        files = dict(data.files)
        rows = files["history.csv"].splitlines(keepends=True)
        rows[1],rows[2] = rows[2],rows[1]
        files["history.csv"] = b"".join(rows)
        with self.assertRaisesRegex(ValueError,"ordering"):
            decode_run(files,"invalid")

    def test_finite_but_inconsistent_flow_rejected(self):
        data = load_run(BASELINE)
        files = dict(data.files)
        rows = files['history.csv'].decode().splitlines()
        values = rows[1].split(',')
        values[4] = '1.0'
        rows[1] = ','.join(values)
        files['history.csv'] = ('\n'.join(rows)+'\n').encode()
        with self.assertRaisesRegex(ValueError,"pressure difference"):
            decode_run(files,"invalid")

    def test_invalid_configuration_rejected(self):
        data = load_run(BASELINE)
        for before,after in ((b'current=2.0',b'current=-2.0'),(b'source=0',b'source=0.5')):
            files = dict(data.files)
            self.assertIn(before,files['config.cfg'])
            files['config.cfg'] = files['config.cfg'].replace(before,after)
            with self.subTest(after=after),self.assertRaises(ValueError):
                decode_run(files,'invalid')

    @unittest.skipUnless((ROOT/"build/physarum_run").is_file(),"Build the C++ engine first")
    def test_fresh_cpp_run(self):
        data = run_experiment(ROOT/"build/physarum_run",{**DEFAULTS,"current":1.,"gamma":2.,"dt":.1,"duration":10.})
        self.assertEqual(len(data.frames),101)
        self.assertAlmostEqual(data.frames[0]["q"][0],2/3,places=12)
        self.assertEqual(data.parameters["gamma"],2)
        self.assertIn("metadata.txt",data.files)


try:
    from PySide6.QtWidgets import QApplication
    from desktop.viewer import Viewer
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE,"Install desktop/requirements.txt and analysis/requirements.txt")
class ViewerStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare_platform_plugins()
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = Viewer(auto_run=False)
        self.window.set_run(load_run(BASELINE))

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_scrub_synchronizes_tables_and_plot(self):
        self.window.timeline.setValue(120)
        frame = self.window.data.frames[120]
        self.assertEqual(self.window.index,120)
        self.assertEqual(self.window.step_spin.value(),120)
        self.assertIn("6.0000",self.window.time_label.text())
        self.assertAlmostEqual(float(self.window.edges_table.item(0,3).text()),frame["d"][0],places=5)
        self.assertEqual(list(self.window.canvas.cursors[0].get_xdata()),[6.,6.])
        self.assertFalse(self.window.playing)

    def test_step_restart_and_end(self):
        self.window.step_forward()
        self.assertEqual(self.window.index,1)
        self.window.scrub(600)
        self.window.step_forward()
        self.assertEqual(self.window.index,600)
        self.window.restart()
        self.assertEqual(self.window.index,0)
        self.assertEqual(self.window.timeline.value(),0)

    def test_draft_parameters_do_not_change_loaded_run(self):
        original = self.window.data.frames[0]["q"][:]
        self.window.controls["current"].setValue(1)
        self.assertEqual(self.window.data.frames[0]["q"],original)
        self.assertIn("differ",self.window.parameter_note.text())
        self.window.defaults()
        self.assertIn("match",self.window.parameter_note.text())

    def test_reverse_flow_visible_without_axis_clipping(self):
        data = load_run(BASELINE)
        data.parameters.update(source=3.,sink=0.)
        for frame in data.frames:
            frame["q"] = [-value for value in frame["q"]]
            reference = frame["p"][0]
            frame["p"] = [reference-value for value in frame["p"]]
        self.window.set_run(data)
        low,high = self.window.canvas.q_axis.get_ylim()
        self.assertLess(low,-2)
        self.assertGreater(high,0)
        self.assertIn("differ",self.window.parameter_note.text())

    def test_playback_uses_discrete_frame(self):
        self.window.toggle_play()
        self.window.last_tick = time.monotonic()-.1
        self.window.tick()
        self.assertIn(self.window.index,(1,2))
        self.assertEqual(self.window.data.frames[self.window.index]["step"],self.window.step_spin.value())
        self.window.scrub(20)
        self.assertFalse(self.window.playing)

    @unittest.skipUnless((ROOT/"build/physarum_run").is_file(),"Build the C++ engine first")
    def test_worker_applies_fresh_run(self):
        self.window.controls["current"].setValue(1.)
        self.window.controls["duration"].setValue(10.)
        self.window.run()
        deadline = time.monotonic()+10
        while not self.window.run_button.isEnabled() and time.monotonic()<deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(self.window.run_button.isEnabled())
        self.assertEqual(self.window.data.parameters["current"],1.)
        self.assertEqual(len(self.window.data.frames),201)
        self.assertAlmostEqual(self.window.data.frames[0]["q"][0],2/3,places=12)


if __name__ == "__main__":
    unittest.main()
