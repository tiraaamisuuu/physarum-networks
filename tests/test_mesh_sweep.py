import csv
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from desktop.mesh_data import DEFAULT_MESH,default_scene
from desktop.mesh_sweep import run_sweep,sweep_plan,load_sweep
def small_scene():
    scene=default_scene();scene['nodes']=[scene['nodes'][i] for i in (0,10,30)];return scene


class SweepTests(unittest.TestCase):
    def test_plan_bounds(self):
        for values,seeds in (([1.8],[42]),([1.8,1.8],[42]),([1.2,1.8],[42,42]),([1.2,1.8],[True]),([1,1.2,1.5,1.8],[1,2,3,4,5,6,7])):
            with self.assertRaises(ValueError):sweep_plan(DEFAULT_MESH,'gamma',values,seeds)
        with self.assertRaises(ValueError):sweep_plan(DEFAULT_MESH,'dt',[.05,.03],[42])
    def test_paired_inputs_and_incremental_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            progress=[];result=run_sweep(small_scene(),dict(DEFAULT_MESH,spacing=1.5,duration=1),'gamma',[1.2,1.8],[42],root=temp,progress=lambda i,n,row:progress.append((i,n,row)))
            self.assertEqual([(i,n) for i,n,_ in progress],[(1,2),(2,2)])
            a,b=[Path(row['run_folder']) for row in result['rows']]
            for name in ('edges.csv','initial.csv','demands.csv'):self.assertEqual((a/'inputs'/name).read_bytes(),(b/'inputs'/name).read_bytes())
            summary=json.loads((Path(result['folder'])/'summary.json').read_text());self.assertTrue(summary['complete']);self.assertEqual(len(summary['rows']),2)
            with (Path(result['folder'])/'summary.csv').open() as stream:self.assertEqual(len(list(csv.DictReader(stream))),2)
            loaded=load_sweep(result['folder']);self.assertTrue(loaded['complete']);self.assertEqual(len(loaded['rows']),2)
            moved=Path(temp)/'moved-study';Path(result['folder']).rename(moved);loaded=load_sweep(moved)
            self.assertTrue(all(Path(row['run_folder']).is_relative_to(moved.resolve()) for row in loaded['rows']))
    def test_cancel_preserves_completed_case(self):
        with tempfile.TemporaryDirectory() as temp:
            cancel=threading.Event()
            with self.assertRaisesRegex(ValueError,'cancelled'):
                run_sweep(small_scene(),dict(DEFAULT_MESH,spacing=1.5,duration=1),'current',[.2,2.],[42],root=temp,cancel=cancel,progress=lambda *_:cancel.set())
            folder=next(Path(temp).iterdir());summary=json.loads((folder/'summary.json').read_text());self.assertFalse(summary['complete']);self.assertEqual(len(summary['rows']),1);self.assertTrue((folder/'failure.txt').exists())
    def test_native_study_handoff(self):
        from desktop.qt_compat import prepare_platform_plugins
        prepare_platform_plugins()
        from PySide6.QtWidgets import QApplication
        from desktop.mesh_viewer import MeshViewer
        app=QApplication.instance() or QApplication([]);window=MeshViewer(auto_run=False)
        window.scene=small_scene();window.refresh_pairs();window.set_settings(dict(DEFAULT_MESH,spacing=1.5,duration=1));panel=window.sweep_panel
        panel.values.setText('1.2, 1.8');panel.seeds.setText('42')
        with tempfile.TemporaryDirectory() as temp:
            def local_sweep(*args,**kwargs):return run_sweep(*args,root=temp,**kwargs)
            with patch('desktop.mesh_sweep_view.run_sweep',local_sweep):
                try:
                    panel.begin();deadline=time.monotonic()+15
                    while panel.running() and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
                    app.processEvents();self.assertFalse(panel.running());self.assertEqual(panel.table.rowCount(),2)
                    panel.table.selectRow(1);panel.open_selected();self.assertEqual(window.run_data.food_count,3);self.assertEqual(window.run_data.settings['gamma'],1.8)
                    self.assertTrue((panel.folder/'study.svg').exists())
                finally:
                    panel.cancel()
                    while panel.running():app.processEvents();time.sleep(.01)
                    window.close();app.processEvents()


if __name__=='__main__':unittest.main()
