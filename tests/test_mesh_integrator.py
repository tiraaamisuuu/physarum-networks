"""Continuous analytic reference and independently checked second pressure stage."""
import copy
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from desktop.mesh_data import ROOT,DEFAULT_MESH,default_scene,run_mesh_experiment,load_mesh_run,solver_extrema,compare_mesh_trajectories


class HeunTests(unittest.TestCase):
    def scalar(self,root,dt,method='heun',switch=False):
        folder=Path(root)/f'{method}-{dt}';folder.mkdir();steps=round(1/dt)
        (folder/'config').write_text(f'dt={dt}\ngamma=2\ncurrent=2\nsteps={steps}\nintegrator={method}\n')
        (folder/'edges').write_text('edge,from,to,length\n0,0,1,3\n');(folder/'initial').write_text('edge,conductivity\n0,0.2\n')
        pairs=[(0,1) if not switch or k<steps//2 else (1,0) for k in range(steps+1)]
        (folder/'demands').write_text('step,source,sink\n'+''.join(f'{k},{a},{b}\n' for k,(a,b) in enumerate(pairs)))
        subprocess.run([str(ROOT/'build/physarum_mesh'),str(folder/'config'),str(folder/'edges'),'2',str(folder/'initial'),str(folder/'demands'),str(folder/'output')],check=True,capture_output=True,timeout=20)
        return folder,steps,pairs
    def test_heun_analytic_and_second_order(self):
        with tempfile.TemporaryDirectory() as temp:
            errors=[]
            for dt in (.1,.05,.025):
                folder,steps,_=self.scalar(temp,dt);d=np.fromfile(folder/'output/D.f64',dtype='<f8')
                factor=1-dt+dt*dt/2;np.testing.assert_allclose(d,.8-.6*factor**np.arange(steps+1),rtol=1e-12,atol=1e-13)
                errors.append(abs(d[-1]-(.8-.6*math.exp(-1))))
            self.assertGreater(errors[0]/errors[1],3.8);self.assertGreater(errors[1]/errors[2],3.8)
    def test_predictor_uses_held_pair_at_switch(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,steps,pairs=self.scalar(temp,.1,switch=True);d=np.fromfile(folder/'output/D.f64',dtype='<f8');q=np.fromfile(folder/'output/Q.f64',dtype='<f8');sq=np.fromfile(folder/'output/stage_Q.f64',dtype='<f8');sp=np.fromfile(folder/'output/stage_P.f64',dtype='<f8').reshape(steps,2)
            signs=np.array([1 if a==0 else -1 for a,b in pairs]);np.testing.assert_allclose(q,2*signs);np.testing.assert_allclose(sq,2*signs[:-1])
            predictor=.9*d[:-1]+.1*.8;np.testing.assert_allclose(sq,predictor/3*(sp[:,0]-sp[:,1]),rtol=1e-12,atol=1e-12)
    def test_euler_legacy_recurrence(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,steps,_=self.scalar(temp,.1,method='euler');d=np.fromfile(folder/'output/D.f64',dtype='<f8');np.testing.assert_allclose(d,.8-.6*.9**np.arange(steps+1),rtol=1e-12,atol=1e-13)
            self.assertFalse((folder/'output/stage_Q.f64').exists())
    def test_cli_preserves_existing_records(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,_,_=self.scalar(temp,.1);before=(folder/'output/D.f64').read_bytes()
            result=subprocess.run([str(ROOT/'build/physarum_mesh'),str(folder/'config'),str(folder/'edges'),'2',str(folder/'initial'),str(folder/'demands'),str(folder/'output')],capture_output=True,text=True,timeout=20)
            self.assertNotEqual(result.returncode,0);self.assertIn('never overwritten',result.stderr);self.assertEqual(before,(folder/'output/D.f64').read_bytes())
    def test_cli_crlf_and_extra_column(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,_,_=self.scalar(temp,.1)
            for name in ('config','edges','initial','demands'):
                path=folder/name;path.write_bytes(path.read_bytes().replace(b'\n',b'\r\n'))
            command=[str(ROOT/'build/physarum_mesh'),str(folder/'config'),str(folder/'edges'),'2',str(folder/'initial'),str(folder/'demands'),str(folder/'crlf')]
            subprocess.run(command,check=True,capture_output=True,timeout=20);self.assertEqual((folder/'output/D.f64').read_bytes(),(folder/'crlf/D.f64').read_bytes())
            (folder/'edges').write_text('edge,from,to,length\n0,0,1,3,\n');command[-1]=str(folder/'invalid');result=subprocess.run(command,capture_output=True,text=True,timeout=20)
            self.assertNotEqual(result.returncode,0);self.assertIn('edge ordering',result.stderr)
    def test_heun_record_stages_and_tamper(self):
        scene=default_scene();scene['nodes']=[scene['nodes'][i] for i in (0,10,30)]
        with tempfile.TemporaryDirectory() as temp:
            r=run_mesh_experiment(scene,dict(DEFAULT_MESH,integrator='heun',dt=.05,spacing=1.5,duration=1),root=temp)
            self.assertEqual(r.stage_q.shape,(20,len(r.mesh['edges'])));self.assertEqual(r.stage_p.shape,(20,len(r.mesh['nodes'])));self.assertEqual(r.stage_diagnostics.shape,(20,7))
            ext=solver_extrema(r);self.assertGreaterEqual(ext['max_conservation'],float(r.stage_diagnostics[:,4].max()))
            k=11;power=np.abs(r.q[k])**r.settings['gamma'];predicted=.95*r.d[k]+.05*power/(1+power);n=len(r.mesh['nodes']);lap=np.zeros((n,n));b=np.zeros(n);b[r.pairs[k,0]]=2;b[r.pairs[k,1]]=-2
            for i,e in enumerate(r.mesh['edges']):
                u,v=e['from'],e['to'];g=predicted[i]/e['length'];lap[u,u]+=g;lap[v,v]+=g;lap[u,v]-=g;lap[v,u]-=g
            np.testing.assert_allclose(r.stage_p[k,1:],np.linalg.solve(lap[1:,1:],b[1:]),rtol=1e-10,atol=1e-10)
            # Tampering the predictor stage must be detected by its physical equations.
            sq=np.memmap(r.folder/'output/stage_Q.f64',dtype='<f8',mode='r+',shape=r.stage_q.shape);sq[5,0]+=.2;sq.flush();del sq
            with self.assertRaisesRegex(ValueError,'Heun stage'):load_mesh_run(r.folder)
    def test_matched_refinement_comparison(self):
        scene=default_scene();scene['nodes']=[scene['nodes'][i] for i in (0,10,30)]
        with tempfile.TemporaryDirectory() as temp:
            a=run_mesh_experiment(scene,dict(DEFAULT_MESH,integrator='heun',dt=.05,spacing=1.5,duration=1),root=temp)
            b=run_mesh_experiment(scene,dict(a.settings,dt=.025),root=temp);comparison=compare_mesh_trajectories(a,b)
            self.assertIsNotNone(comparison);self.assertAlmostEqual(comparison['max_D_difference'],float(np.abs(a.d-b.d[::2]).max()))
            b.settings['gamma']=1.2;self.assertIsNone(compare_mesh_trajectories(a,b));b.settings['gamma']=a.settings['gamma']
            b.pairs=b.pairs.copy();b.pairs[1]=b.pairs[1][::-1];self.assertIsNone(compare_mesh_trajectories(a,b))


if __name__=='__main__':unittest.main()
