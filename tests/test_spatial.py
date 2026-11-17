"""Independent checks for spatial preparation, scheduled C++ flow and record integrity."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
from desktop.spatial_data import (ROOT,DEFAULT_SETTINGS,default_scene,intersects,hits_rectangle,
    build_graph,demand_schedule,load_spatial_run,run_spatial_experiment)


def synthetic_scene():
    points=[(0.,0.),(2.,0.),(0.,2.),(2.,2.),(1.,3.)]
    nodes=[{'key':str(i),'name':f'Node {i}','kind':'station','x':x,'y':y,'lat':51.,'lon':0.} for i,(x,y) in enumerate(points)]
    return {'schema_version':1,'name':'Synthetic mathematical fixture','nodes':nodes,'barriers':[],
            'geography':{'river':[{'xy_km':[[1.,-2.],[1.,5.]]}],
                         'elevation':{'x':[-1.,3.],'y':[-1.,4.],'metres':[[0.,0.],[0.,0.]]},
                         'station_catalog':[],'sources':[]}}


class GeometryTest(unittest.TestCase):
    def test_segments(self):
        self.assertTrue(intersects((0,0),(2,2),(0,2),(2,0)))
        self.assertTrue(intersects((0,0),(2,0),(1,0),(3,0)))
        self.assertFalse(intersects((0,0),(1,0),(2,0),(3,0)))
        self.assertFalse(intersects((0,0),(2,0),(0,1),(2,1)))
        self.assertTrue(hits_rectangle((0,0),(4,4),(1,1,2,2)))
        self.assertTrue(hits_rectangle((1.5,1.5),(1.7,1.7),(1,1,2,2)))
        self.assertFalse(hits_rectangle((0,0),(4,0),(1,1,2,2)))

    def test_geography_snapshot(self):
        scene=default_scene();geography=scene['geography']
        self.assertEqual(len(scene['nodes']),46)
        self.assertEqual(len(geography['station_catalog']),272)
        self.assertEqual(geography['projection']['crs'],'EPSG:27700')
        self.assertTrue(all(51.<node['lat']<52 and -.5<node['lon']<.1 for node in scene['nodes']))
        self.assertEqual(np.array(geography['elevation']['metres']).shape,(13,19))
        self.assertEqual(geography['elevation']['role'],'visual_context_only')
        self.assertTrue(geography['river'])

    def test_cost_and_overlay_separation(self):
        scene=synthetic_scene();settings={**DEFAULT_SETTINGS,'neighbours':2}
        edges,_=build_graph(scene,settings)
        for edge in edges:
            self.assertAlmostEqual(edge['length'],edge['distance_km']+(2. if edge['river_crossing'] else 0))
        self.assertTrue(any(edge['river_crossing'] for edge in edges))
        changed=copy.deepcopy(scene);changed['geography']['elevation']['metres']=[[9000.,9000.],[9000.,9000.]]
        self.assertEqual(edges,build_graph(changed,settings)[0])
        flat,_=build_graph(scene,{**settings,'river_penalty':0.})
        self.assertEqual([(e['from'],e['to']) for e in flat],[(e['from'],e['to']) for e in edges])
        for edge in flat:self.assertEqual(edge['length'],edge['distance_km'])

    def test_incomplete_river_coverage_rejected(self):
        scene=default_scene();scene['nodes'][0]['lon']=-.6
        with self.assertRaisesRegex(ValueError,'outside the cached Thames coverage'):
            build_graph(scene,DEFAULT_SETTINGS)

    def test_restrictions_do_not_silently_add_links(self):
        scene=synthetic_scene();scene['barriers']=[[.9,-10.,1.1,10.]]
        with self.assertRaisesRegex(ValueError,'separates demand stations'):build_graph(scene,DEFAULT_SETTINGS)
        scene=synthetic_scene();scene['nodes'][1]['x']=scene['nodes'][0]['x'];scene['nodes'][1]['y']=scene['nodes'][0]['y']
        with self.assertRaisesRegex(ValueError,'same position'):build_graph(scene,DEFAULT_SETTINGS)

    def test_demand_schedule_reproducible_and_station_only(self):
        scene=synthetic_scene();scene['nodes'][-1]['kind']='junction'
        first=demand_schedule(scene,DEFAULT_SETTINGS,50)
        self.assertEqual(first,demand_schedule(scene,DEFAULT_SETTINGS,50))
        self.assertNotEqual(first,demand_schedule(scene,{**DEFAULT_SETTINGS,'seed':43},50))
        self.assertTrue(all(a!=b and 4 not in (a,b) for a,b in first))
        fixed=demand_schedule(scene,{**DEFAULT_SETTINGS,'demand_mode':'fixed_pair','source_id':'0','sink_id':'3'},5)
        self.assertEqual(fixed,[(0,3)]*6)


@unittest.skipUnless((ROOT/'build/physarum_run').is_file(),'Build the C++ engine first')
class SpatialIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory()
        cls.settings={**DEFAULT_SETTINGS,'duration':1.,'dt':.1,'neighbours':3}
        cls.dataset=run_spatial_experiment(ROOT/'build/physarum_run',synthetic_scene(),cls.settings,cls.directory.name)
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def test_arbitrary_graph_pressure_matches_independent_numpy(self):
        run=self.dataset;n=len(run.scene['nodes']);matrix=np.zeros((n,n))
        for edge in run.edges:
            a,b=edge['from'],edge['to'];weight=.5/edge['length']
            matrix[a,a]+=weight;matrix[b,b]+=weight;matrix[a,b]-=weight;matrix[b,a]-=weight
        source,sink=run.sources[0],run.sinks[0]
        demand=np.zeros(n);demand[source]=2.;demand[sink]=-2.
        kept=[i for i in range(n) if i!=sink]
        pressure=np.zeros(n);pressure[kept]=np.linalg.solve(matrix[np.ix_(kept,kept)],demand[kept])
        np.testing.assert_allclose(run.p[0],pressure,atol=1e-11,rtol=1e-11)
        self.assertEqual(run.d.shape,(11,len(run.edges)))
        self.assertLess(run.diagnostics[:,0].max(),1e-11)

    def test_recorded_schedule_replay_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as temporary:
            other=run_spatial_experiment(ROOT/'build/physarum_run',synthetic_scene(),self.settings,temporary)
            self.assertEqual((self.dataset.folder/'output/history.csv').read_bytes(),(other.folder/'output/history.csv').read_bytes())
            self.assertEqual((self.dataset.folder/'inputs/demands.csv').read_bytes(),(other.folder/'inputs/demands.csv').read_bytes())

    def test_invalid_cli_schedule_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);bad=root/'demands.csv';bad.write_text('step,source,sink\n0,0,0\n')
            result=subprocess.run([str(ROOT/'build/physarum_run'),str(self.dataset.folder/'inputs/input.cfg'),str(root/'output'),
                str(self.dataset.folder/'inputs/edges.csv'),'5',str(bad)],capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse((root/'output').exists())

    def test_euler_corruption_detected_after_physical_flow_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            import shutil
            folder=Path(temporary)/'copy';shutil.copytree(self.dataset.folder,folder)
            path=folder/'output/history.csv';raw=np.loadtxt(path,delimiter=',',skiprows=1)
            m=len(self.dataset.edges);raw[m:2*m,3]*=1.1;raw[m:2*m,5:7]/=1.1
            header=path.read_text().splitlines()[0]
            np.savetxt(path,raw,delimiter=',',header=header,comments='',fmt='%.17g')
            with self.assertRaisesRegex(ValueError,'Euler update'):load_spatial_run(folder)


try:
    from PySide6.QtWidgets import QApplication
    from desktop.qt_compat import prepare_platform_plugins
    from desktop.spatial_viewer import SpatialViewer
    QT_AVAILABLE=True
except ImportError:QT_AVAILABLE=False


@unittest.skipUnless(QT_AVAILABLE,'Install desktop dependencies')
class GeographicViewerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):prepare_platform_plugins();cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.window=SpatialViewer(auto_run=False)
    def tearDown(self):self.window.close();self.app.processEvents()

    def test_preview_is_distinct_from_a_run(self):
        self.assertIsNone(self.window.run_data)
        self.assertFalse(self.window.play_button.isEnabled())
        self.assertIn('PREVIEW',self.window.title.text())
        self.assertEqual(len(self.window.canvas.xy),46)

    def test_display_overlay_does_not_change_geometry(self):
        old=copy.deepcopy(self.window.scene)
        self.window.toggle_terrain(False);self.window.toggle_names(True)
        self.assertEqual(self.window.scene,old)
        self.assertFalse(self.window.canvas.terrain.get_visible())

    @unittest.skipUnless((ROOT/'build/physarum_run').is_file(),'Build C++ engine')
    def test_real_london_run_and_synchronized_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            run=run_spatial_experiment(ROOT/'build/physarum_run',default_scene(),{**DEFAULT_SETTINGS,'duration':1.},temporary)
            self.window.set_run(run);self.window.scrub(10)
            self.assertEqual(self.window.index,10)
            self.assertEqual(self.window.step_spin.value(),10)
            self.assertEqual(list(self.window.canvas.cursors[0].get_xdata()),[.5,.5])
            self.assertAlmostEqual(float(self.window.edge_table.item(0,4).text()),run.d[10,0],places=5)
            self.window.pick('edge',3);self.assertEqual(self.window.canvas.selected_edge,3)
            self.window.scrub(11)
            self.assertAlmostEqual(self.window.canvas.markers[0].get_ydata()[0],run.d[11,3])
            from desktop.viewer import number
            self.assertIn('D='+number(run.d[11,3]),self.window.selection_label.text())
            self.window.pick('node',0);self.window.scrub(12)
            self.assertIn('p='+number(run.p[12,0]),self.window.selection_label.text())
            self.window.scene['barriers']=[];self.window.preview()
            self.assertIsNone(self.window.run_data);self.assertFalse(self.window.play_button.isEnabled())
            self.assertNotIn('p=',self.window.selection_label.text())


if __name__=='__main__':unittest.main()
