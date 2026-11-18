"""Independent equations, topology, protocol, records and native controls."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import numpy as np
from desktop.mesh_data import (ROOT,DEFAULT_MESH,MeshRun,default_scene,build_mesh,mesh_demands,mesh_metrics,
    load_mesh_run,run_mesh_experiment,validate_mesh_settings)
from desktop.mesh_plot import export_snapshot,tube_widths


def small_scene():
    scene=default_scene();scene['nodes']=[scene['nodes'][i] for i in (0,10,30)];return scene


class MeshProtocolTests(unittest.TestCase):
    def test_refinement_keeps_demands(self):
        scene=default_scene();a=dict(DEFAULT_MESH,duration=1,dt=.05);b=dict(a,dt=.025)
        self.assertEqual(mesh_demands(scene,a),mesh_demands(scene,b)[::2])
        self.assertEqual(build_mesh(small_scene(),a),build_mesh(small_scene(),b))
    def test_exact_food_and_barriers(self):
        scene=small_scene();s=dict(DEFAULT_MESH,spacing=1.5,duration=1);mesh=build_mesh(scene,s)
        self.assertEqual(mesh['nodes'][:3],scene['nodes']);self.assertTrue(all(any(e['from']==i or e['to']==i for e in mesh['edges']) for i in range(3)))
        for e in mesh['edges']:
            a,b=mesh['nodes'][e['from']],mesh['nodes'][e['to']]
            self.assertAlmostEqual(e['distance_km'],np.hypot(a['x']-b['x'],a['y']-b['y']))
        # Block one food location: no fabricated link is inserted to rescue it.
        x,y=scene['nodes'][0]['x'],scene['nodes'][0]['y'];scene['barriers']=[[x-.1,y-.1,x+.1,y+.1]]
        with self.assertRaises(ValueError):build_mesh(scene,s)
    def test_invalid_protocol(self):
        for update in (dict(dt=.03),dict(gamma=float('nan')),dict(switch_interval=.073),dict(seed=True)):
            with self.assertRaises(ValueError):validate_mesh_settings(dict(DEFAULT_MESH,**update))
        s=dict(DEFAULT_MESH,demand_mode='fixed_pair',source_id='missing')
        with self.assertRaises(ValueError):mesh_demands(default_scene(),s)
    def test_fixed_pair(self):
        scene=small_scene();s=dict(DEFAULT_MESH,duration=1,demand_mode='fixed_pair',source_id=scene['nodes'][0]['key'],sink_id=scene['nodes'][2]['key'])
        self.assertEqual(set(mesh_demands(scene,s)),{(0,2)})
    def test_obstacle_segments_are_removed(self):
        from desktop.spatial_data import hits_rectangle
        scene=small_scene();s=dict(DEFAULT_MESH,spacing=1.5,duration=1);mesh=build_mesh(scene,s)
        xy=np.array([[n['x'],n['y']] for n in mesh['nodes']])
        edge=next(e for e in mesh['edges'] if e['from']>=3 and e['to']>=3)
        x,y=xy[[edge['from'],edge['to']]].mean(axis=0);rect=[x-.1,y-.1,x+.1,y+.1];scene['barriers']=[rect]
        blocked=build_mesh(scene,s);points=np.array([[n['x'],n['y']] for n in blocked['nodes']])
        self.assertFalse(any(hits_rectangle(points[e['from']],points[e['to']],rect) for e in blocked['edges']))
    def test_imported_weighted_pairs_and_refinement(self):
        from desktop.mesh_data import import_pair_weights
        scene=small_scene()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'demand.csv';path.write_text(f"source,sink,weight\n{scene['nodes'][0]['key']},{scene['nodes'][1]['key']},1\n{scene['nodes'][0]['key']},{scene['nodes'][2]['key']},3\n")
            loaded=import_pair_weights(scene,path);s=dict(DEFAULT_MESH,duration=30,dt=.05,demand_mode='weighted_pairs');pairs=mesh_demands(loaded,s)
            self.assertEqual(pairs,mesh_demands(loaded,dict(s,dt=.025))[::2]);self.assertTrue(all(a==0 and b in (1,2) for a,b in pairs))
            self.assertTrue(.65<sum(b==2 for a,b in pairs)/len(pairs)<.85)
            self.assertNotIn('weighted_demand',scene);self.assertEqual(loaded['weighted_demand']['filename'],'demand.csv')
    def test_invalid_weighted_pairs(self):
        from desktop.mesh_data import import_pair_weights
        scene=small_scene()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'bad.csv'
            for text in ('source,sink,weight\n','source,sink,weight\nmissing,missing,1\n',f"source,sink,weight\n{scene['nodes'][0]['key']},{scene['nodes'][1]['key']},-1\n",f"source,sink,weight\n{scene['nodes'][0]['key']},{scene['nodes'][0]['key']},1\n"):
                path.write_text(text)
                with self.assertRaises(ValueError):import_pair_weights(scene,path)
        with self.assertRaisesRegex(ValueError,'Import a CSV'):mesh_demands(scene,dict(DEFAULT_MESH,demand_mode='weighted_pairs'))


class MetricTests(unittest.TestCase):
    def run_for(self,cycle=False):
        nodes=[dict(name=str(i),x=x,y=y) for i,(x,y) in enumerate([(0.,0.),(1.,0.),(1.,1.)])]
        edges=[dict(id=0,**{'from':0,'to':1},distance_km=1),dict(id=1,**{'from':1,'to':2},distance_km=1)]
        if cycle:edges.append(dict(id=2,**{'from':0,'to':2},distance_km=2**.5))
        return MeshRun({}, {},dict(nodes=nodes,edges=edges,food_count=3),np.array([0.]),np.ones((1,len(edges))),None,None,None,None,Path('.'))
    def test_tree(self):
        r=self.run_for();m=mesh_metrics(r,0,.1,True)
        self.assertTrue(m['all_food_connected']);self.assertEqual(m['length_km'],2);self.assertEqual(m['single_break_survival'],0)
        self.assertAlmostEqual(m['mean_route_km'],4/3);self.assertAlmostEqual(m['mean_route_direct_ratio'],(2+2**.5)/3);self.assertAlmostEqual(m['terminal_mst_km'],2)
        self.assertEqual(m['critical_bridge_length_km'],2);self.assertAlmostEqual(m['expected_connected_pair_fraction_after_break'],1/3);self.assertAlmostEqual(m['worst_break_connected_pair_fraction'],1/3)
    def test_cycle_and_cutoff(self):
        r=self.run_for(True);m=mesh_metrics(r,0,.1,True);self.assertEqual(m['single_break_survival'],1);self.assertEqual(m['mean_route_direct_ratio'],1)
        r.d[0]=[1,.001,.001];before=r.d.copy();m=mesh_metrics(r,0,.1,True)
        self.assertEqual(m['largest_food_component'],2);self.assertEqual(m['connected_pair_fraction'],1/3);self.assertIsNone(m['mean_route_km']);np.testing.assert_array_equal(before,r.d)
        self.assertEqual(m['expected_connected_pair_fraction_after_break'],0);self.assertEqual(m['worst_break_connected_pair_fraction'],0)
    def test_width_fixed_radius_scale(self):np.testing.assert_allclose(tube_widths([.5,.5/16]),[1.2,.6])


class MeshRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.record=run_mesh_experiment(small_scene(),dict(DEFAULT_MESH,integrator='euler',dt=.05,spacing=1.5,duration=1),root=cls.temp.name)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_numpy_pressure_solve(self):
        r=self.record;n=len(r.mesh['nodes']);k=13;lap=np.zeros((n,n));b=np.zeros(n);b[r.pairs[k,0]]=r.settings['current'];b[r.pairs[k,1]]=-r.settings['current']
        for i,e in enumerate(r.mesh['edges']):
            u,v=e['from'],e['to'];g=r.d[k,i]/e['length'];lap[u,u]+=g;lap[v,v]+=g;lap[u,v]-=g;lap[v,u]-=g
        expected=np.linalg.solve(lap[1:,1:],b[1:]);np.testing.assert_allclose(r.p[k,1:],expected,rtol=1e-10,atol=1e-10)
    def test_weighted_run_reopens(self):
        scene=small_scene();scene['weighted_demand']={'pairs':[dict(source=scene['nodes'][0]['key'],sink=scene['nodes'][1]['key'],weight=1.)]}
        r=run_mesh_experiment(scene,dict(DEFAULT_MESH,spacing=1.5,duration=1,demand_mode='weighted_pairs'),root=self.temp.name)
        self.assertTrue(np.array_equal(r.pairs,np.tile([0,1],(len(r.times),1))));self.assertEqual(load_mesh_run(r.folder).settings['demand_mode'],'weighted_pairs')
    def test_tamper_detected(self):
        target=Path(self.temp.name)/'tampered';shutil.copytree(self.record.folder,target)
        d=np.memmap(target/'output/D.f64',dtype='<f8',mode='r+',shape=self.record.d.shape);d[10,0]*=2;d.flush();del d
        with self.assertRaises(ValueError):load_mesh_run(target)
    def test_source_snapshot_integrity_and_archive(self):
        from desktop.mesh_data import archive_source_snapshot
        target=Path(self.temp.name)/'source-tamper';shutil.copytree(self.record.folder,target)
        source=target/'source/src/mesh_main.cpp';self.assertTrue(source.is_file());source.write_text(source.read_text()+'\n// changed\n')
        with self.assertRaisesRegex(ValueError,'Source snapshot checksum'):load_mesh_run(target)
        a,b=Path(self.temp.name)/'source-a.tar.gz',Path(self.temp.name)/'source-b.tar.gz'
        archive_source_snapshot(self.record.folder,a);archive_source_snapshot(self.record.folder,b);self.assertEqual(a.read_bytes(),b.read_bytes())
    def test_compiled_source_fingerprint_binding(self):
        from desktop.growth_data import sha256_file
        target=Path(self.temp.name)/'fingerprint-tamper';shutil.copytree(self.record.folder,target);path=target/'scenario.json';manifest=json.loads(path.read_text());manifest['software']['engine_source_fingerprint']='0'*64;path.write_text(json.dumps(manifest))
        checks=json.loads((target/'checksums.json').read_text());checks['scenario.json']=sha256_file(path);(target/'checksums.json').write_text(json.dumps(checks))
        with self.assertRaisesRegex(ValueError,'Compiled-source fingerprint'):load_mesh_run(target)
    def test_food_attachment_detected(self):
        target=Path(self.temp.name)/'moved';shutil.copytree(self.record.folder,target);path=target/'scenario.json';m=json.loads(path.read_text());m['mesh']['nodes'][0]['x']+=.01;path.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'exact recorded mesh vertex'):load_mesh_run(target)
    def test_export(self):
        target=Path(self.temp.name)/'snapshot';record=export_snapshot(self.record,20,target)
        self.assertEqual(record['state'],20)
        for name in ('network.svg','network.png','snapshot.json','nodes.csv','tubes.csv'):self.assertTrue((target/name).stat().st_size>100)
    def test_native_view(self):
        from desktop.qt_compat import prepare_platform_plugins
        prepare_platform_plugins()
        from PySide6.QtWidgets import QApplication
        from desktop.mesh_viewer import MeshViewer
        app=QApplication.instance() or QApplication([]);window=MeshViewer(auto_run=False);window.accept_run(self.record);window.display(20);app.processEvents()
        self.assertIn('t = 1',window.state_label.text());self.assertEqual(window.food_table.rowCount(),3)
        self.assertEqual(len(window.canvas.links.get_segments()),int((self.record.d[20]>=window.cutoff.currentData()).sum()))
        window.controls['gamma'].setValue(1.2);window.draft();self.assertIn('DESIGN CHANGED',window.banner.text())
        window.final_state();self.assertIn('SNAPSHOT ANALYSIS',window.selection.text())
        # Geographic design edits must never mutate a displayed record.
        window.scene=copy.deepcopy(self.record.scene);before=copy.deepcopy(self.record.scene)
        from desktop.spatial_data import within_coverage
        available=next(n for n in window.scene['geography']['station_catalog'] if within_coverage(n,window.scene['geography']) and n['tfl_id'] not in {x['key'] for x in window.scene['nodes']})
        window.toggle_station(available['tfl_id']);self.assertEqual(len(window.scene['nodes']),4);self.assertEqual(self.record.scene,before)
        self.assertEqual(int(window.layout_panel.canvas.selected.sum()),4)
        window.layout_panel.overlay('elevation',True);window.restriction_mode(True);self.assertTrue(window.layout_panel.canvas.drawing)
        window.restriction_mode(False);window.close();app.processEvents()


if __name__=='__main__':unittest.main()
