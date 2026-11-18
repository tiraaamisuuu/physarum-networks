"""Growth record integrity, scientific semantics and native state synchronization."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest

import numpy as np
from desktop.growth_data import ROOT,DEFAULT_GROWTH,default_scene,prepare_growth,run_growth_experiment,load_growth_run

ENGINE=ROOT/'build/physarum_growth'


class GrowthPreparationTest(unittest.TestCase):
    def test_foods_are_real_coordinates_and_start_is_selected(self):
        foods,pixels,extent,blocked,river,config=prepare_growth(default_scene(),DEFAULT_GROWTH)
        self.assertEqual(len(foods),46);self.assertEqual(config['width'],480)
        start=next(i for i,node in enumerate(foods) if node['key']==DEFAULT_GROWTH['start_id'])
        np.testing.assert_allclose(pixels[start],[config['initial_x'],config['initial_y']])
        self.assertTrue((blocked==0).all());self.assertGreater(river.sum(),0)
        self.assertEqual(blocked.shape,river.shape)
        self.assertGreater(extent[1],extent[0]);self.assertGreater(extent[3],extent[2])

    def test_invalid_start_masks_and_schedule(self):
        for change in ({'start_id':'not-a-station'},{'steps':103},{'decay':float('nan')},{'division_interval':0}):
            with self.assertRaises(ValueError):prepare_growth(default_scene(),{**DEFAULT_GROWTH,**change})
        scene=default_scene();node=next(n for n in scene['nodes'] if n['key']==DEFAULT_GROWTH['start_id'])
        scene['barriers']=[[node['x']-.1,node['y']-.1,node['x']+.1,node['y']+.1]]
        with self.assertRaisesRegex(ValueError,'inside a restricted'):prepare_growth(scene,DEFAULT_GROWTH)

    def test_surface_elevation_does_not_change_growth_inputs(self):
        scene=default_scene();altered=copy.deepcopy(scene)
        altered['geography']['elevation']['metres']=(np.array(altered['geography']['elevation']['metres'])+5000).tolist()
        a,b=prepare_growth(scene,DEFAULT_GROWTH),prepare_growth(altered,DEFAULT_GROWTH)
        for i in (1,3,4):np.testing.assert_array_equal(a[i],b[i])
        self.assertEqual(a[2],b[2]);self.assertEqual(a[5],b[5])


@unittest.skipUnless(ENGINE.is_file(),'Build C++ growth engine')
class GrowthIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory();cls.settings={**DEFAULT_GROWTH,'width':160,'steps':100,'seed_count':80,'max_agents':500}
        cls.dataset=run_growth_experiment(default_scene(),cls.settings,cls.temporary.name)
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def test_population_and_contact_semantics(self):
        run=self.dataset
        self.assertEqual(len(run.stats),11);self.assertEqual(run.stats[0,2],80)
        np.testing.assert_array_equal(run.stats[:,2],80+run.stats[:,6]-run.stats[:,7])
        np.testing.assert_array_equal(run.occupied.sum(axis=(1,2)),run.stats[:,2])
        self.assertTrue(np.all(np.diff(run.stats[:,3])>=0));self.assertTrue((run.trail>=0).all())
        self.assertEqual(int(run.stats[-1,3]),int((run.contacts>=0).sum()))
        self.assertLess(np.count_nonzero(run.trail[0]),run.trail.shape[1]*run.trail.shape[2]/20)

    def test_exact_seeded_replay(self):
        other=run_growth_experiment(default_scene(),self.settings,self.temporary.name)
        for file in ('trail.f32','occupied.u8','stats.csv','food.csv'):
            self.assertEqual((self.dataset.folder/'output'/file).read_bytes(),(other.folder/'output'/file).read_bytes())

    def copy_run(self,root):
        target=Path(root)/'copy';shutil.copytree(self.dataset.folder,target);return target

    def test_truncated_field_and_population_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=self.copy_run(temporary);path=folder/'output/trail.f32'
            with path.open('r+b') as stream:stream.truncate(path.stat().st_size-4)
            with self.assertRaisesRegex(ValueError,'Incomplete growth field'):load_growth_run(folder)
        with tempfile.TemporaryDirectory() as temporary:
            folder=self.copy_run(temporary);path=folder/'output/stats.csv'
            raw=np.loadtxt(path,skiprows=1,delimiter=',');raw[1,2]+=1
            np.savetxt(path,raw,delimiter=',',header=path.read_text().splitlines()[0],comments='',fmt='%.17g')
            with self.assertRaisesRegex(ValueError,'population accounting'):load_growth_run(folder)

    def test_missing_checksum_and_nonfinite_trail_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=self.copy_run(temporary);(folder/'checksums.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'Incomplete growth checksums'):load_growth_run(folder)
        with tempfile.TemporaryDirectory() as temporary:
            folder=self.copy_run(temporary);path=folder/'output/trail.f32'
            with path.open('r+b') as stream:stream.write(np.array([np.nan],dtype='<f4').tobytes())
            with self.assertRaisesRegex(ValueError,'Nonfinite/negative'):load_growth_run(folder)


try:
    from PySide6.QtWidgets import QApplication
    from desktop.qt_compat import prepare_platform_plugins
    from desktop.growth_viewer import GrowthViewer,explain_growth
    QT_AVAILABLE=True
except ImportError:QT_AVAILABLE=False


@unittest.skipUnless(QT_AVAILABLE and ENGINE.is_file(),'Install Qt and build growth engine')
class GrowthViewerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare_platform_plugins();cls.app=QApplication.instance() or QApplication([])
        cls.temporary=tempfile.TemporaryDirectory()
        cls.dataset=run_growth_experiment(default_scene(),{**DEFAULT_GROWTH,'steps':100,'width':160},cls.temporary.name)
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()
    def setUp(self):self.window=GrowthViewer(auto_run=False)
    def tearDown(self):self.window.close();self.app.processEvents()

    def test_preview_and_replay_synchronize_fields_and_explanation(self):
        window=self.window;self.assertIsNone(window.run_data);self.assertFalse(window.play_button.isEnabled())
        window.set_run(self.dataset);window.scrub(4)
        self.assertEqual(window.frame.value(),4);self.assertEqual(window.timeline.value(),4)
        np.testing.assert_array_equal(window.canvas.image.get_array(),self.dataset.trail[4])
        self.assertEqual(window.canvas.cursors[0].get_xdata(),[40,40])
        self.assertIn('Update 40',window.time_label.text());self.assertEqual(window.phase.text(),explain_growth(self.dataset,4)[0])
        window.pick_food(3);window.scrub(0);self.assertIn(self.dataset.foods[3]['name'],window.selected.text())
        if self.dataset.contacts[3]>0:self.assertIn('not yet visited',window.selected.text())
        window.scrub(10);window.next_frame.click();self.assertEqual(window.index,10)
        window.set_run(self.dataset);self.assertNotIn('not yet visited',window.selected.text())
        window.preview();self.assertFalse(window.play_button.isEnabled());self.assertNotIn('first visited',window.selected.text())

    def test_controls_are_drafts_and_particle_overlay_preserves_record(self):
        window=self.window;window.set_run(self.dataset);old=self.dataset.trail[2].copy()
        window.controls['seed'].setValue(13)
        self.assertEqual(window.run_data.settings['seed'],42);self.assertIn('next experiment',window.statusBar().currentMessage())
        window.toggle_agents(True);window.toggle_names(True);window.scrub(2)
        np.testing.assert_array_equal(self.dataset.trail[2],old);self.assertTrue(window.canvas.agent_image.get_visible())
        window.reset();self.assertIsNone(window.run_data);self.assertEqual(window.start.currentData(),DEFAULT_GROWTH['start_id'])

    def test_close_cancels_worker_without_destroying_a_running_thread(self):
        window=self.window;window.show();window.controls['steps'].setValue(4000);window.run();window.close()
        deadline=time.monotonic()+10
        while (window.worker.isRunning() or window.timer.isActive()) and time.monotonic()<deadline:
            self.app.processEvents();time.sleep(.02)
        self.assertFalse(window.worker.isRunning());self.assertFalse(window.timer.isActive())


if __name__=='__main__':unittest.main()
