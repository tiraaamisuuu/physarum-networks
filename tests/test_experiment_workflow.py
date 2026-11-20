"""Geometry preview and map interactions must preserve recorded numerical data."""
import copy
from pathlib import Path
import tempfile
import unittest
import numpy as np
from desktop.mesh_data import DEFAULT_MESH,prepare_mesh_experiment,run_mesh_experiment
from desktop.scene_design import example_scene,SANDBOX_EXAMPLES,edit_barrier,DesignHistory
from desktop.spatial_data import hits_rectangle


class ExperimentWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.scene=example_scene('obstacle')
        cls.settings=dict(DEFAULT_MESH,spacing=1.,dt=.05,duration=20.,demand_mode='fixed_pair',source_id='sandbox-west',sink_id='sandbox-east')
        cls.record=run_mesh_experiment(cls.scene,cls.settings,root=cls.temp.name)
        from desktop.qt_compat import prepare_platform_plugins
        prepare_platform_plugins()
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def window(self):
        from desktop.mesh_viewer import MeshViewer
        w=MeshViewer(auto_run=False);w.commit_design(copy.deepcopy(self.scene),True);w.set_settings(self.settings);w.accept_run(self.record);w.show();self.app.processEvents();self.addCleanup(w.close);return w
    def click_food(self,w,k):
        from matplotlib.backend_bases import MouseEvent
        c=w.canvas;c.draw();self.app.processEvents();p=c.map.transData.transform(c.xy[k]);c.callbacks.process('button_press_event',MouseEvent('button_press_event',c,*p,button=1));self.app.processEvents()
    def test_preview_matches_actual_inputs_and_recording_size(self):
        before=copy.deepcopy(self.scene);p=prepare_mesh_experiment(self.scene,self.settings);self.assertEqual(p['mesh'],self.record.mesh);self.assertEqual(p['states'],len(self.record.times));np.testing.assert_array_equal(p['pairs'],self.record.pairs)
        raw=sum(f.stat().st_size for f in (self.record.folder/'output').glob('*.f64'));self.assertEqual(p['raw_bytes'],raw);self.assertEqual(self.scene,before)
        points=np.array([[n['x'],n['y']] for n in p['mesh']['nodes']])
        for edge in p['mesh']['edges']:self.assertFalse(hits_rectangle(points[edge['from']],points[edge['to']],self.scene['barriers'][0]))
    def test_block_edit_is_validated_and_undoable(self):
        old=copy.deepcopy(self.scene);edited=edit_barrier(old,0,bounds=[7,3,9,7]);self.assertEqual(old,self.scene);history=DesignHistory();history.push(old);self.assertEqual(history.undo(edited),old)
        self.assertEqual(edit_barrier(old,0,remove=True)['barriers'],[])
        for rect in ([1,4,3,6],[7,2,6,8],[7,-1,9,8],[7,2,float('nan'),8]):
            with self.assertRaises(ValueError):edit_barrier(old,0,bounds=rect)
        with self.assertRaises(ValueError):edit_barrier(old,-1,remove=True)
    def test_examples_are_stable_valid_candidate_experiments(self):
        for key,(_,_,mode) in SANDBOX_EXAMPLES.items():
            with self.subTest(key=key):
                scene=example_scene(key);self.assertEqual(scene,example_scene(key));settings=dict(self.settings,demand_mode=mode,source_id=scene['nodes'][0]['key'],sink_id=scene['nodes'][-1]['key']);p=prepare_mesh_experiment(scene,settings);self.assertEqual(p['mesh']['nodes'][:len(scene['nodes'])],scene['nodes'])
                if mode=='random_pairs':self.assertGreater(len(set(np.asarray(p['pairs']).flat)),2)
    def test_map_route_two_clicks_and_replot_preserve_record(self):
        w=self.window();before=self.record.d.copy();scene=copy.deepcopy(self.record.scene);w.toolbar.zoom();w.route_pick.setChecked(True);self.assertFalse(w.toolbar.mode)
        self.click_food(w,0);self.assertEqual(w.route_pick_start,0);self.assertEqual(w.canvas.route_foods,[0]);self.click_food(w,0);self.assertIsNone(w.current_route)
        w.replot();self.app.processEvents();self.assertTrue(w.canvas.route_markers[0].get_visible());self.click_food(w,1);self.assertIsNotNone(w.current_route);self.assertFalse(w.route_pick.isChecked());self.assertEqual(w.canvas.route_foods,[0,1]);self.assertEqual(self.record.scene,scene);np.testing.assert_array_equal(self.record.d,before)
        w.clear_route();self.assertEqual(w.canvas.route_foods,[]);self.assertIsNone(w.current_route)
    def test_reexport_removes_stale_optional_data(self):
        from desktop.mesh_plot import export_snapshot
        from desktop.mesh_routes import retained_route
        from desktop.mesh_data import archive_source_snapshot
        folder=Path(self.temp.name)/'optional-route';r=self.record;frame=len(r.times)-1;route=retained_route(r,frame,0,1,1e-4)
        export_snapshot(r,frame,folder,route=route);self.assertTrue((folder/'route.csv').exists());export_snapshot(r,frame,folder)
        self.assertFalse((folder/'route.csv').exists())
        legacy=Path(self.temp.name)/'legacy';legacy.mkdir();(legacy/'scenario.json').write_text('{"software":{}}')
        self.assertTrue((folder/'source.tar.gz').exists());archive_source_snapshot(legacy,folder/'source.tar.gz');self.assertFalse((folder/'source.tar.gz').exists())
    def test_playback_does_not_fabricate_route_clicks(self):
        w=self.window();w.selected_pick=('food',0);w.route_pick.setChecked(True);w.display(0);self.assertIsNone(w.route_pick_start);self.assertFalse(w.route_enabled)
        self.click_food(w,0);w.route_escape.activated.emit();self.assertFalse(w.route_pick.isChecked());self.assertEqual(w.canvas.route_foods,[])
    def test_preview_invalidates_and_block_table_edits_draft_only(self):
        w=self.window();panel=w.layout_panel;w.tabs.setCurrentWidget(panel);panel.preview_paths();self.assertEqual(panel.prepared['mesh'],self.record.mesh);self.assertIsNotNone(panel.canvas.preview_mesh)
        panel.barrier_table.item(0,1).setText('3');self.assertEqual(w.scene['barriers'][0][1],3);self.assertEqual(self.record.scene['barriers'][0][1],2);self.assertIsNone(panel.prepared);self.assertIsNone(panel.canvas.preview_mesh)
        w.undo_design();self.assertEqual(w.scene['barriers'],self.record.scene['barriers']);panel.preview_paths();w.controls['dt'].setValue(.025);self.assertIsNone(panel.prepared)
        w.set_settings(self.settings);w.set_barrier(0,[7,0,9,10]);panel.preview_paths();self.assertIsNone(panel.prepared);self.assertIn('disconnect',panel.preview_status.text())
    def test_example_load_restores_coherent_controls_and_tool_exits_zoom(self):
        w=self.window();w.controls['dt'].setValue(.00625);w.load_example('network');self.assertEqual(len(w.scene['nodes']),8);self.assertEqual(w.settings()['demand_mode'],'random_pairs');self.assertEqual(w.settings()['dt'],DEFAULT_MESH['dt']);self.assertEqual(w.source.currentData(),w.scene['nodes'][0]['key'])
        panel=w.layout_panel;panel.tools.setCurrentIndex(1);panel.canvas.toolbar.zoom();panel.tools.activated.emit(1);self.assertFalse(panel.canvas.toolbar.mode)


if __name__=='__main__':unittest.main()
