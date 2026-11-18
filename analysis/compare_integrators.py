#!/usr/bin/env python3
"""Compare Euler and recorded two-stage Heun under identical London forcing."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import numpy as np
from matplotlib.figure import Figure
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop.mesh_data import ROOT,load_mesh_run,run_mesh_experiment,mesh_metrics,solver_extrema,archive_source_snapshot
from desktop.growth_data import sha256_file
from desktop.mesh_plot import draw_tubes,snapshot_figure
from analysis.replay_mesh_case import replay_case


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'results/integration_validation');parser.add_argument('--refresh',action='store_true',help='Refresh existing local Heun runs and measurements.');args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    previous=json.loads((args.output/'validation.json').read_text()) if args.refresh else None
    old=json.loads((ROOT/'results/mesh_validation/validation.json').read_text());euler=[]
    for name in ('default','half_dt','quarter_dt'):
        path=ROOT/old['runs'][name]['run_folder']
        if path.exists():r=load_mesh_run(path)
        else:
            root=ROOT/'results/mesh_runs';root.mkdir(parents=True,exist_ok=True)
            r=replay_case(ROOT/'results/mesh_validation/replay'/name,Path(tempfile.mkdtemp(prefix='replayed-euler-',dir=root)),False)
        euler.append(r)
    base=euler[0]
    heun=[];cases={}
    for dt in (.05,.025,.0125,.00625):
        name=f'heun-{dt:g}'
        r=load_mesh_run(ROOT/previous['cases'][name]['run_folder']) if previous and name in previous['cases'] else run_mesh_experiment(base.scene,dict(base.settings,dt=dt,integrator='heun'));heun.append(r)
        assert r.mesh==base.mesh
        np.testing.assert_array_equal(r.d[0],base.d[0]);np.testing.assert_array_equal(r.pairs[::round(.05/dt)],base.pairs)
        case=args.output/'replay'/name;case.mkdir(parents=True,exist_ok=True)
        with gzip.open(case/'scenario.json.gz','wb') as stream:stream.write((r.folder/'scenario.json').read_bytes())
        shutil.copytree(r.folder/'inputs',case/'inputs',dirs_exist_ok=True);shutil.copyfile(r.folder/'checksums.json',case/'original-checksums.json')
        archive_source_snapshot(r.folder,case/'source.tar.gz')
        states=np.unique(np.linspace(0,len(r.times)-1,4).astype(int));np.savez_compressed(case/'reference.npz',states=states,d=r.d[states],q=r.q[states],p=r.p[states])
        cases[name]=dict(settings=r.settings,run_folder=str(r.folder.relative_to(ROOT)),diagnostics=solver_extrema(r),final=mesh_metrics(r,len(r.times)-1,routes=True))
        print(name,cases[name],flush=True)
    comparisons={}
    for name,runs in [('euler',euler),('heun',heun)]:
        a,b,c=runs[:3];x=np.abs(a.d-b.d[::2]);y=np.abs(b.d[::2]-c.d[::4]);diff_fine=np.abs(a.d-c.d[::4])
        comparisons[name]=dict(max_transient_coarse_half=float(x.max()),max_transient_half_quarter=float(y.max()),refinement_ratio=float(x.max()/y.max()),final_coarse_half=float(x[-1].max()),final_half_quarter=float(y[-1].max()),coarse_quarter_max=float(diff_fine.max()))
    # Compare both coarse methods to the same finite Heun reference, not two different targets.
    reference=heun[-1].d[::8]
    for name,r in [('euler',euler[0]),('heun',heun[0])]:comparisons[name]['max_difference_to_common_fine_heun']=float(np.max(np.abs(r.d-reference)))
    default=heun[2];fine=heun[3];delta=np.abs(default.d-fine.d[::2])
    default_check=dict(dt=.0125,reference_dt=.00625,max_transient_D_difference=float(delta.max()),final_D_max_difference=float(delta[-1].max()),retained_segments_identical_at_1e_4=bool(np.array_equal(default.d[-1]>=1e-4,fine.d[-1]>=1e-4)))
    report=dict(model='Tero_2010_sigmoid_mesh_v1',generator_sha256=sha256_file(Path(__file__)),metric_source_sha256=sha256_file(ROOT/'desktop/mesh_data.py'),forcing='Identical mesh, initial D and food pairs at aligned model times. Switch interval .05 is fixed. Both Heun stages use the held pair, including at switch boundaries.',cases=cases,comparison=comparisons,interactive_default_refinement=default_check,limitations='Finite-reference refinement, not exact London error. Topology is cutoff-dependent and may bifurcate. Numerical improvement does not establish biological calibration or transport feasibility.')
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print('COMPARISON',comparisons,flush=True)
    figure=Figure(figsize=(10,4),dpi=160,layout='constrained');axes=figure.subplots(1,2)
    for name,runs,color in [('Euler',euler,'#a87438'),('Heun',heun,'#287e67')]:
        a,b,c=runs[:3];ratio=round(.05/heun[-1].settings['dt']);axes[0].plot(base.times,np.max(np.abs(a.d-heun[-1].d[::ratio]),axis=1),label=name,color=color,lw=1.3)
        errors=[comparisons[name.lower()]['max_transient_coarse_half'],comparisons[name.lower()]['max_transient_half_quarter']]
        axes[1].loglog([.05,.025],errors,'o-',label=name,color=color)
    axes[0].set(xlabel='Model time',ylabel='Maximum |D coarse − D fine Heun|');axes[1].set(xlabel='Coarser Δt in each comparison',ylabel='Maximum transient refinement difference')
    for axis in axes:axis.spines[['top','right']].set_visible(False);axis.grid(alpha=.15);axis.legend(frameon=False)
    figure.suptitle('Integration sensitivity · same London graph and forcing',fontsize=12)
    figure.savefig(ROOT/'docs/assets/integration-sensitivity.png',dpi=180)
    write_default_figures(default)
    text=f'''# Integration comparison

Both methods solve the same Tero sigmoid ODE on the same London graph, initial conductivities and held food-pair sequence. Heun uses a second pressure solve at its Euler predictor, then averages two Euler stages. Every stage is recorded and independently checked for the pressure law, conservation, work/dissipation and solver acceptance; this is not post-processing of Euler output.

| Method | Max D difference: dt .05 vs .025 | Max D difference: dt .025 vs .0125 | Ratio | Coarse difference to common fine Heun |
| --- | ---: | ---: | ---: | ---: |
'''
    for name in ('euler','heun'):
        c=comparisons[name];text+=f"| {name} | {c['max_transient_coarse_half']:.6g} | {c['max_transient_half_quarter']:.6g} | {c['refinement_ratio']:.4g} | {c['max_difference_to_common_fine_heun']:.6g} |\n"
    text+=f'''\nInteractive default Heun Δt = 0.0125 versus 0.00625: maximum transient D difference {default_check['max_transient_D_difference']:.6g}, final maximum difference {default_check['final_D_max_difference']:.6g}. Final retained edge sets at D ≥ 10⁻⁴ are identical: {default_check['retained_segments_identical_at_1e_4']}. This is a finite check for this setup, not a general convergence guarantee.\n'''
    text+='''
These are finite-reference differences, not known exact London errors. Separate scalar CLI tests compare with an exact continuous solution and verify first/second-order behaviour. Holding the pair for both Heun stages is essential at demand-switch boundaries. Neither method is a biological calibration, proof of an optimal network or an engineering model.

Heun is expressed as convex Euler steps: D* = (1−dt)D + dt f(Q), followed by D_next = ½D + ½[(1−dt)D* + dt f(Q*)]. For the supported dt ≤ 0.25, positive conductivities remain positive in exact arithmetic; finite-state/underflow checks remain active. There is no numerical floor or pruning. Legacy four-key Euler configs and archived histories remain supported.

The public replay archives preserve exact graph, initial state, forcing and numerical reference snapshots. Replay with `analysis/replay_mesh_case.py CASE`. `validation.json` records full metrics and diagnostic extrema across accepted states **and predictor stages**. Figure: `docs/assets/integration-sensitivity.png`. Complete dynamic runs remain local under `results/mesh_runs/`.
'''
    (args.output/'REPORT.md').write_text(text)


def write_default_figures(run):
    assets=ROOT/'docs/assets';figure=snapshot_figure(run,len(run.times)-1)
    def save(figure,name):
        for extension in ('png','svg'):
            path=assets/f'{name}.{extension}';figure.savefig(path,dpi=180)
            if extension=='svg':path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    save(figure,'tube-network')
    figure=Figure(figsize=(12,8),dpi=160,layout='constrained',facecolor='white')
    for axis,time in zip(figure.subplots(2,2).flat,(0,3,10,30)):
        index=round(time/run.settings['dt']);draw_tubes(axis,run,index);metrics=mesh_metrics(run,index)
        axis.set_title(f"t = {time:g} · {metrics['largest_food_component']}/46 connected · {metrics['length_km']:.1f} km",fontsize=10,loc='left')
    figure.suptitle('London · flow-driven tube adaptation on a fine spatial mesh',fontsize=14)
    figure.supxlabel(f"{run.settings.get('integrator','euler')} · Δt = {run.settings['dt']:g} · γ = 1.8 · I₀ = 2 · seed 42 · D ≥ 10⁻⁴ · width ∝ D¼\nTfL coordinates · © OpenStreetMap contributors · model time, not biological hours",fontsize=8)
    save(figure,'tube-evolution')
    source=json.loads((run.folder/'scenario.json').read_text());paths=[assets/f'{name}.{ext}' for name in ('tube-network','tube-evolution') for ext in ('png','svg')]
    import matplotlib
    provenance=dict(public_replay_case='results/integration_validation/replay/heun-0.0125',settings=run.settings,software=source['software'],figure_generator_sha256=sha256_file(Path(__file__)),plot_libraries=dict(numpy=np.__version__,matplotlib=matplotlib.__version__),raw_checksums=json.loads((run.folder/'checksums.json').read_text()),figure_sha256={p.name:sha256_file(p) for p in paths},interpretation='Actual accepted C++ states; exact food vertices; cutoff 1e-4; fixed fourth-root width scale; no curve smoothing or biological-hour calibration.')
    (assets/'tube-default.json').write_text(json.dumps(provenance,indent=2)+'\n')

if __name__=='__main__':main()
