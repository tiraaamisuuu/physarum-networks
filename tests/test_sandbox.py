import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from desktop.scene_design import sandbox_scene,sandbox_example,edit_food,DesignHistory,is_sandbox
from desktop.spatial_data import validate_scene,hits_rectangle
from desktop.mesh_data import DEFAULT_MESH,build_mesh,run_mesh_experiment,load_mesh_run,default_scene
from desktop.mesh_routes import retained_route
from desktop.mesh_plot import export_snapshot

class SandboxDesign(unittest.TestCase):
    def test_local_sites_are_exact_and_geographically_honest(self):
        empty=sandbox_scene();scene,key=edit_food(empty,x=2.,y=3.);scene,_=edit_food(scene,x=14.,y=7.);mesh=build_mesh(scene,dict(DEFAULT_MESH,spacing=1.))
        self.assertEqual(empty['nodes'],[]);self.assertEqual(mesh['food_count'],2);self.assertEqual(mesh['nodes'][:2],scene['nodes']);self.assertNotIn('lat',scene['nodes'][0]);self.assertTrue(all(0<=n['x']<=16 and 0<=n['y']<=10 for n in mesh['nodes']))
        moved,_=edit_food(scene,key,x=3.,name='My starting food');self.assertEqual(moved['nodes'][0]['key'],key);self.assertEqual(scene['nodes'][0]['x'],2.);validate_scene(moved)
    def test_station_coordinates_stay_fixed(self):
        s=default_scene();node=s['nodes'][0]
        with self.assertRaisesRegex(ValueError,'Official station'):edit_food(s,node['key'],x=node['x']+.1)
        custom,key=edit_food(s,x=531.,y=180.);food=next(n for n in custom['nodes'] if n['key']==key);self.assertEqual(food['kind'],'food');self.assertIn('lat',food);self.assertNotIn('tfl_id',food);validate_scene(custom)
    def test_edit_rejections(self):
        s=sandbox_example()
        for kwargs in (dict(x=8,y=5),dict(x=-1,y=1),dict(x=float('nan'),y=2),dict(x=2,y=5),dict(x=3,y=3,name='East food')):
            with self.assertRaises(ValueError):edit_food(s,**kwargs)
    def test_undo_redo_restores_geometry_and_keys(self):
        a=sandbox_scene();b,key=edit_food(a,x=2,y=3);history=DesignHistory();history.push(a);c,_=edit_food(b,key,x=4);history.push(b);b2=history.undo(c);self.assertEqual(b2,b);self.assertEqual(history.redo(b2),c);history.push(b);self.assertEqual(history.redo_stack,[])

class SandboxExperiment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();scene=sandbox_example();settings=dict(DEFAULT_MESH,spacing=1.,duration=20.,dt=.05,demand_mode='fixed_pair',source_id=scene['nodes'][0]['key'],sink_id=scene['nodes'][1]['key']);cls.record=run_mesh_experiment(scene,settings,root=cls.temp.name)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_actual_path_detours_without_crossing_blocked_area(self):
        r=self.record;route=retained_route(r,len(r.times)-1,0,1,1e-4);self.assertIsNotNone(route);self.assertGreater(route['length_km'],12.5);self.assertEqual(route['foods'],['West food','East food'])
        xy=np.array([[n['x'],n['y']] for n in r.mesh['nodes']])
        for k in route['edges']:
            e=r.mesh['edges'][k];self.assertFalse(hits_rectangle(xy[e['from']],xy[e['to']],r.scene['barriers'][0]));self.assertGreaterEqual(r.d[-1,k],1e-4)
        self.assertLess(r.diagnostics[:,4].max(),1e-9);self.assertTrue(is_sandbox(load_mesh_run(r.folder).scene))
    def test_no_route_is_not_fabricated(self):self.assertIsNone(retained_route(self.record,0,0,1,10.))
    def test_export_contains_real_route_and_correct_attribution(self):
        r=self.record;route=retained_route(r,len(r.times)-1,0,1,1e-4);folder=Path(self.temp.name)/'snapshot';export=export_snapshot(r,len(r.times)-1,folder,names=True,route=route);self.assertEqual(export['coordinate_reference'],'local_km');self.assertEqual(export['route'],route)
        with (folder/'route.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),len(route['edges']));self.assertIn('User-designed', (folder/'network.svg').read_text());self.assertNotIn('TfL coordinates',(folder/'network.svg').read_text())
        reverse=retained_route(r,len(r.times)-1,1,0,1e-4);export_snapshot(r,len(r.times)-1,folder,route=reverse)
        with (folder/'route.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual(int(rows[0]['from']),1);self.assertEqual(int(rows[-1]['to']),0)
        for row in rows:
            sign=1 if row['from']==row['recorded_from'] else -1
            self.assertAlmostEqual(float(row['Q_along_route']),sign*float(row['Q_recorded']))
    def test_native_editor_route_and_record_immutability(self):
        from desktop.qt_compat import prepare_platform_plugins
        prepare_platform_plugins()
        from PySide6.QtWidgets import QApplication
        from matplotlib.backend_bases import MouseEvent
        from desktop.mesh_viewer import MeshViewer
        app=QApplication.instance() or QApplication([]);w=MeshViewer(auto_run=False);w.workspace.setCurrentIndex(1);self.assertEqual(w.scene['nodes'],[]);self.assertFalse(w.compute_button.isEnabled());w.add_food(2,5);w.add_food(14,5);self.assertTrue(w.compute_button.isEnabled());key=w.scene['nodes'][0]['key'];w.rename_food(key,'West hub');w.move_food(key,3,5);w.undo_design();self.assertEqual(w.scene['nodes'][0]['x'],2);w.redo_design();self.assertEqual(w.scene['nodes'][0]['x'],3)
        r=self.record;before=copy.deepcopy(r.scene);w.scene=copy.deepcopy(r.scene);w.refresh_pairs();w.set_settings(r.settings);w.accept_run(r);self.assertEqual(w.index,len(r.times)-1);w.show();app.processEvents();w.show_route();self.assertIsNotNone(w.current_route);self.assertGreater(len(w.canvas.route_line.get_xdata()),2);w.tabs.setCurrentWidget(w.layout_panel);self.assertTrue(w.measurements.isHidden());self.assertTrue(w.playback.isHidden());self.assertIn('Place and name',w.narrative.text());w.layout_panel.refresh(True);w.layout_panel.tools.setCurrentIndex(1);app.processEvents();canvas=w.layout_panel.canvas;canvas.draw();px,py=canvas.axis.transData.transform((5.,1.));event=MouseEvent('button_press_event',canvas,px,py,button=1);canvas.click(event);self.assertEqual(len(w.scene['nodes']),3);self.assertEqual(r.scene,before);self.assertIn('DESIGN CHANGED',w.banner.text());w.undo_design();self.assertEqual(len(w.scene['nodes']),2);w.close();app.processEvents()
if __name__=='__main__':unittest.main()
