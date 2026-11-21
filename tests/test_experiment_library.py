import copy
from contextlib import closing
import csv
import json
from pathlib import Path
import shutil
import sqlite3
import os
import tempfile
import time
import unittest
import numpy as np
from desktop.experiment_catalog import ExperimentCatalog,discover_experiments,record_key,scenario_key
from desktop.experiment_comparison import comparison_data,export_comparison
from desktop.mesh_data import DEFAULT_MESH,run_mesh_experiment,sha256_file
from desktop.scene_design import example_scene


class ExperimentLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);scene=example_scene('obstacle');settings=dict(DEFAULT_MESH,spacing=1.,duration=4.,dt=.05,demand_mode='fixed_pair',source_id='sandbox-west',sink_id='sandbox-east')
        cls.base=run_mesh_experiment(scene,settings,root=cls.root/'results/mesh_runs');cls.changed=run_mesh_experiment(scene,dict(settings,gamma=1.15),root=cls.root/'results/mesh_runs');cls.fine=run_mesh_experiment(scene,dict(settings,dt=.025),root=cls.root/'results/mesh_runs');cls.low=run_mesh_experiment(scene,dict(settings,current=.2),root=cls.root/'results/mesh_runs')
        scene=example_scene('network');cls.network=run_mesh_experiment(scene,dict(settings,demand_mode='random_pairs'),root=cls.root/'results/mesh_runs')
        from desktop.qt_compat import prepare_platform_plugins
        prepare_platform_plugins()
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.catalog=ExperimentCatalog(self.root/self._testMethodName)
    def wait(self,condition,timeout=20):
        deadline=time.monotonic()+timeout
        while not condition() and time.monotonic()<deadline:self.app.processEvents();time.sleep(.01)
        self.app.processEvents();self.assertTrue(condition(),'Timed out waiting for native worker state.')
    def window(self):
        from desktop.mesh_viewer import MeshViewer
        w=MeshViewer(auto_run=False,catalog=self.catalog);w.install_record(self.base);w.show();self.app.processEvents()
        def cleanup():
            w.library.note_dirty=False;w.close();self.wait(lambda:not w.library.running());self.app.processEvents()
        self.addCleanup(cleanup);return w
    def test_annotations_are_transactional_and_do_not_modify_records(self):
        key=record_key(self.base);before={str(p.relative_to(self.base.folder)):sha256_file(p) for p in self.base.folder.rglob('*') if p.is_file()}
        self.assertEqual(self.catalog.annotations(),{});self.assertFalse(self.catalog.path.exists());self.catalog.save(key,dict(title='Control <A> & $B$',notes='Observe branches.\nNo optimality claim.',favorite=True));other=ExperimentCatalog(self.catalog.root);self.assertTrue(other.annotation(key)['favorite'])
        with self.assertRaises(ValueError):other.save(key,dict(notes='x'*8001))
        self.assertIn('Observe branches',self.catalog.annotation(key)['notes']);self.assertEqual(before,{str(p.relative_to(self.base.folder)):sha256_file(p) for p in self.base.folder.rglob('*') if p.is_file()})
        with closing(sqlite3.connect(self.catalog.path)) as con,con:con.execute('PRAGMA user_version=99')
        with self.assertRaises(ValueError):self.catalog.annotations()
    def test_discovery_distinguishes_metadata_from_verified_records(self):
        catalog=ExperimentCatalog(self.root);rows=discover_experiments(catalog)['rows'];self.assertEqual(len(rows),5);self.assertTrue(all(r['status']=='Verify on open' for r in rows));self.assertFalse(catalog.path.exists())
        folder=self.catalog.root/'results/mesh_runs/20260101T120000-incomplete';folder.mkdir(parents=True);shutil.copyfile(self.base.folder/'scenario.json',folder/'scenario.json');rows=discover_experiments(self.catalog)['rows'];self.assertEqual(rows[0]['status'],'Incomplete')
        (folder/'scenario.json').write_text('not JSON');self.assertEqual(discover_experiments(self.catalog)['rows'][0]['status'],'Unreadable')
    def test_labels_follow_scenario_identity_when_a_folder_is_copied(self):
        self.catalog.save(record_key(self.base),dict(title='My control',favorite=True));moved=self.catalog.root/'copied-experiment';moved.mkdir(parents=True);shutil.copyfile(self.base.folder/'scenario.json',moved/'scenario.json');self.catalog.remember(moved);row=discover_experiments(self.catalog)['rows'][0];self.assertEqual(row['title'],'My control');self.assertTrue(row['annotation']['favorite']);self.assertEqual(scenario_key(moved),record_key(self.base))
    def test_parameter_comparison_reports_actual_matching_conditions(self):
        data=comparison_data(self.base,self.changed,1e-4);self.assertTrue(all(data['conditions'].values()));self.assertEqual([r['key'] for r in data['changes']],['gamma']);self.assertIsNone(data['numerical'])
        for row in data['measurements']:
            if row['reference'] is not None and row['current'] is not None:self.assertAlmostEqual(row['delta'],row['current']-row['reference'])
    def test_different_food_populations_withhold_measurement_deltas(self):
        data=comparison_data(self.base,self.network,1e-4);self.assertFalse(data['conditions']['same_food_sites']);self.assertTrue(all(row['delta'] is None for row in data['measurements']));self.assertIn('Food sites differ',data['summary'])
    def test_pair_schedule_is_distinguished_from_injected_flow(self):
        data=comparison_data(self.base,self.low,1e-4);self.assertTrue(data['conditions']['same_food_pair_schedule']);self.assertFalse(data['conditions']['same_injected_current']);self.assertFalse(data['conditions']['same_held_forcing']);self.assertEqual([r['key'] for r in data['changes']],['current'])
    @unittest.skipUnless(hasattr(os,'mkfifo'),'Requires a POSIX pipe to simulate an unresponsive disk file.')
    def test_metadata_scan_times_out_without_trapping_a_worker(self):
        from desktop.library_io import scan_catalog
        import threading
        folder=self.catalog.root/'results/mesh_runs/20260101T120000-slow';folder.mkdir(parents=True);os.mkfifo(folder/'scenario.json');start=time.monotonic();result=scan_catalog(self.catalog,threading.Event(),idle_timeout=.5);self.assertTrue(result['partial']);self.assertLess(time.monotonic()-start,4)
    def test_refinement_export_keeps_inputs_and_user_notes_separate(self):
        from desktop.comparison_view import ComparisonPanel
        w=self.window();w.install_record(self.fine);w.pin_reference(self.base);data=w.comparison.data;self.assertIsNotNone(data['numerical']);folder=self.catalog.root/'export'
        export_comparison(self.base,self.fine,data,w.comparison.figure,folder,dict(reference=dict(title='<control> & $literal$',notes='My hypothesis')))
        result=json.loads((folder/'comparison.json').read_text());self.assertEqual(result['reference']['scenario_sha256'],record_key(self.base));self.assertEqual(result['user_annotations']['reference']['title'],'<control> & $literal$')
        with (folder/'measurements.csv').open() as f:self.assertEqual(len(list(csv.DictReader(f))),5)
        for name in ('comparison.png','comparison.svg','reference-scenario.json','current-scenario.json','reference-source.tar.gz','current-source.tar.gz'):self.assertGreater((folder/name).stat().st_size,100)
        from desktop.mesh_plot import export_snapshot
        snapshot=self.catalog.root/'snapshot';export_snapshot(self.base,0,snapshot,annotation=dict(title='Local note'));self.assertTrue((snapshot/'experiment-notes.json').exists());export_snapshot(self.base,0,snapshot);self.assertFalse((snapshot/'experiment-notes.json').exists())
    def test_native_library_search_save_and_favorites(self):
        for r in (self.base,self.changed,self.network):self.catalog.remember(r.folder)
        w=self.window();p=w.library;w.tabs.setCurrentWidget(p);self.wait(lambda:len(p.rows)==3 and not p.running());p.title.setText('Control <A> & $B$');p.notes.setPlainText('Useful comparison');p.favorite.setChecked(True);self.assertTrue(p.save_notes());key=p.selected['key'];self.assertEqual(self.catalog.annotation(key)['title'],'Control <A> & $B$')
        p.search.setText('useful comparison');self.assertEqual(p.table.rowCount(),1);p.favorites.setChecked(True);self.assertEqual(p.table.rowCount(),1);p.search.setText('does not exist');self.assertEqual(p.table.rowCount(),0);self.assertFalse(p.open_button.isEnabled())
    def test_pinned_reference_survives_new_runs_and_maps_share_scale(self):
        w=self.window();w.pin_reference(self.base);w.install_record(self.changed);w.install_record(self.fine);self.assertIs(w.previous,self.base);self.assertTrue(w.reference_pinned);axes=w.comparison.figure.axes;self.assertEqual(axes[0].get_xlim(),axes[1].get_xlim());self.assertEqual(axes[0].get_ylim(),axes[1].get_ylim());axes[0].set_xlim(1,10);self.assertEqual(axes[0].get_xlim(),axes[1].get_xlim());w.install_record(self.fine);w.automatic_reference();self.assertIs(w.previous,self.changed);self.assertFalse(w.reference_pinned)
    def test_library_reference_check_keeps_selection_workflow_open(self):
        self.catalog.remember(self.changed.folder);w=self.window();p=w.library;w.tabs.setCurrentWidget(p);self.wait(lambda:bool(p.rows) and not p.running());current=w.run_data;p.open_selected('reference');self.wait(lambda:not p.running());self.assertTrue(w.reference_pinned);self.assertEqual(record_key(w.previous),record_key(self.changed));self.assertIs(w.run_data,current);self.assertIs(w.tabs.currentWidget(),p);self.assertIn('Reference pinned',p.status.text())
    def test_failed_async_open_preserves_current_record_and_draft(self):
        bad=self.catalog.root/'bad';shutil.copytree(self.base.folder,bad);(bad/'checksums.json').write_text('{}');w=self.window();draft=copy.deepcopy(w.scene);before=w.run_data;w.tabs.setCurrentWidget(w.library);w.library.open_path(bad);self.assertFalse(w.compute_button.isEnabled());self.wait(lambda:not w.library.running());self.assertIs(w.run_data,before);self.assertEqual(w.scene,draft);self.assertIn('Could not open experiment',w.library.status.text());self.assertTrue(w.compute_button.isEnabled())
    def test_closing_cancels_background_work_without_destroying_live_thread(self):
        w=self.window();p=w.library
        def task(cancel):
            while not cancel.is_set():time.sleep(.005)
            return None
        p.start('open',task,lambda _:self.fail('Cancelled work must not install a result.'));w.close();self.wait(lambda:not p.running() and not w.isVisible());self.assertFalse(w.timer.isActive())


if __name__=='__main__':unittest.main()
