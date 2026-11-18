import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from desktop.biology_data import ROOT,DEFAULT_BIOLOGY,make_biology_mesh,segment_inside,geometry,run_biology,load_biology,validate_biology,sha

class BiologicalRecords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)/'record'
        cls.record=run_biology(dict(DEFAULT_BIOLOGY,duration=8.,save_interval=2.),folder=cls.folder)
    @classmethod
    def tearDownClass(cls):cls.record=None;cls.temp.cleanup()
    def test_geometry_and_zero_normal_flux_weights(self):
        for arena,expected in [('snake',350),('straight',200)]:
            m=make_biology_mesh(dict(DEFAULT_BIOLOGY,arena=arena));self.assertAlmostEqual(m['mass'].sum(),expected,places=10)
            self.assertGreater(m['mass'].min(),0);self.assertGreaterEqual(m['edges'][:,3].min(),0)
        _,rectangles=geometry('snake')
        self.assertFalse(segment_inside(np.array([10.,5.]),np.array([15.,10.]),rectangles))
        self.assertTrue(segment_inside(np.array([25.,5.]),np.array([30.,5.]),rectangles))
    def test_record_and_body_gating(self):
        r=load_biology(self.folder);self.assertEqual(r['fields']['c'].shape[0],5)
        self.assertEqual(len(r['probe']),401);self.assertLess(r['engine']['max_fluid_residual'],1e-9)
        e=r['edges'][:,:2].astype(int);outside=(r['fields']['w'][-1,e].mean(axis=1)<=1)&~r['inoculum'][e].any(axis=1)
        np.testing.assert_array_equal(r['fields']['d'][-1,outside],0)
    def test_source_checksum(self):
        p=self.folder/'source/src/BiologyModel.cpp';old=p.read_bytes()
        try:
            p.write_bytes(old+b'\n');self.assertRaisesRegex(ValueError,'source checksum',load_biology,self.folder)
        finally:p.write_bytes(old)
    def test_raw_checksum(self):
        p=self.folder/'raw/d.f64';old=p.read_bytes()
        try:
            p.write_bytes(old[:-8]);self.assertRaisesRegex(ValueError,'checksum',load_biology,self.folder)
        finally:p.write_bytes(old)
    def test_gating_rejects_rehashed_physical_corruption(self):
        p=self.folder/'raw/d.f64';scenario=self.folder/'scenario.json';old=p.read_bytes();old_manifest=scenario.read_bytes();r=self.record;e=r['edges'][:,:2].astype(int);j=int(np.flatnonzero(~r['inoculum'][e].any(axis=1))[0]);values=np.frombuffer(old,dtype='<f8').copy().reshape(r['fields']['d'].shape);values[-1,j]=.001
        try:
            p.write_bytes(values.tobytes());manifest=json.loads(old_manifest);manifest['files']['raw/d.f64']=sha(p);scenario.write_text(json.dumps(manifest));self.assertRaisesRegex(ValueError,'body gate',load_biology,self.folder)
        finally:p.write_bytes(old);scenario.write_bytes(old_manifest)
    def test_limits(self):
        for change in ({'hill':2},{'dt':0.},{'duration':100000},{'save_interval':.11},{'seed':True}):
            self.assertRaises(ValueError,validate_biology,dict(DEFAULT_BIOLOGY,**change))
    def test_plot_and_native_frame(self):
        from desktop.qt_compat import prepare_platform_plugins
        prepare_platform_plugins()
        from PySide6.QtWidgets import QApplication
        from desktop.biology_viewer import BiologyViewer
        app=QApplication.instance() or QApplication([]);w=BiologyViewer(auto_run=False);w.accept(self.record);w.slider.setValue(4);w.follow.setChecked(False);w.mode.setCurrentIndex(1);app.processEvents()
        self.assertEqual(w.index,4);self.assertIn('t = 8',w.frame_label.text());self.assertIn('Hill exponent: 4',w.stats.text());w.close();app.processEvents()

class IndependentFluidCheck(unittest.TestCase):
    def test_numpy_compliant_storage_balance(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'nodes.csv').write_text('id,x,y,mass,inoculum\n0,0,0,.5,1\n1,.7,0,1,0\n2,2,0,.5,0\n');(p/'edges.csv').write_text('id,from,to,length,weight\n0,0,1,.7,1\n1,1,2,1.3,1\n')
            subprocess.run([str(ROOT/'build/physarum_biology'),str(p/'nodes.csv'),str(p/'edges.csv'),'8','.02','4','.01','20','.02','0',str(p/'out')],check=True,capture_output=True)
            s={name:np.fromfile(p/'out'/(name+'.f64'),dtype='<f8').reshape(-1,2 if name in ('q','d') else 3) for name in ('c','v','p','q','d')}
            B=np.array([[1,0],[-1,1],[0,-1]],float);length=np.array([.7,1.3]);dt=.02
            for k in (0,1,10,150):
                d=s['d'][k];v=.5*(s['v'][k+1,:2]+s['v'][k+1,1:]);L=length/(10+5*np.sqrt(d));R=length/(2.5+13.5*d);C=(.1+.03*d**.75)/length*(1+.01*v);a=(L-dt*R/2)/(L+dt*R/2);b=dt/2/(L+dt*R/2)
                forcing=(s['c'][k]+s['c'][k+1])/2-7
                A=np.eye(3)+dt/2*B@np.diag(b/C)@B.T
                rhs=s['p'][k]-dt*forcing-dt/2*B@(((1+a)*s['q'][k]+b*(B.T@s['p'][k]))/C)
                expected=np.linalg.solve(A,rhs);np.testing.assert_allclose(s['p'][k+1],expected,atol=2e-12,rtol=1e-12)
                flux=a*s['q'][k]+b*(B.T@(s['p'][k]+expected));np.testing.assert_allclose(s['q'][k+1],flux,atol=2e-12,rtol=1e-12)
if __name__=='__main__':unittest.main()
