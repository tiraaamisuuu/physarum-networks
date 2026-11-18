#!/usr/bin/env python3
"""Recorded London sensitivity study, not a Tokyo reproduction or calibration."""
import argparse
import json
import gzip
import shutil
from pathlib import Path
import sys
import time
import numpy as np
from matplotlib.figure import Figure
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop.mesh_data import ROOT,DEFAULT_MESH,default_scene,run_mesh_experiment,load_mesh_run,mesh_metrics,effective_mesh_settings,solver_extrema,archive_source_snapshot
from desktop.mesh_plot import draw_tubes,snapshot_figure
from desktop.growth_data import sha256_file


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'results/mesh_validation');parser.add_argument('--refresh',action='store_true',help='Revalidate existing local raw runs and refresh metrics/figures without rerunning the solver.');args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    scene=default_scene();results={};runs={}
    previous=json.loads((args.output/'validation.json').read_text()) if args.refresh else None
    # Preserve this published Euler baseline even as the interactive default improves.
    baseline=dict(DEFAULT_MESH,integrator='euler',dt=.05)
    configurations={'default':baseline,'half_dt':dict(baseline,dt=.025),'quarter_dt':dict(baseline,dt=.0125),'finer_mesh':dict(baseline,spacing=.3),'seed43':dict(baseline,seed=43),'seed47':dict(baseline,seed=47),'low_current':dict(baseline,current=.2),'low_gamma':dict(baseline,gamma=1.15),'river_cost':dict(baseline,river_penalty=2.)}
    for name,settings in configurations.items():
        start=time.monotonic();r=load_mesh_run(ROOT/previous['runs'][name]['run_folder']) if previous else run_mesh_experiment(scene,settings);runs[name]=r
        if effective_mesh_settings(r.settings)!=effective_mesh_settings(settings) or r.scene!=scene:raise ValueError('Configuration or scene changed; recompute the study without --refresh.')
        elapsed=previous['runs'][name]['seconds'] if previous else time.monotonic()-start
        results[name]=dict(settings=settings,run_folder=str(r.folder.relative_to(ROOT)),nodes=len(r.mesh['nodes']),edges=len(r.mesh['edges']),seconds=elapsed,
            max_conservation=float(r.diagnostics[:,4].max()),max_backward_error=float(r.diagnostics[:,5].max()),min_scaled_rcond_estimate=float(r.diagnostics[:,6].min()),
            final=[mesh_metrics(r,len(r.times)-1,c,True) for c in (1e-5,1e-4,1e-3)])
        results[name].update(solver_extrema(r))
        # Freeze candidate geometry and forcing, not just seeds; triangulation can vary by library version.
        case=args.output/'replay'/name;case.mkdir(parents=True,exist_ok=True)
        with gzip.open(case/'scenario.json.gz','wb') as stream:stream.write((r.folder/'scenario.json').read_bytes())
        shutil.copytree(r.folder/'inputs',case/'inputs',dirs_exist_ok=True)
        states=np.unique(np.linspace(0,len(r.times)-1,4).astype(int))
        np.savez_compressed(case/'reference.npz',states=states,d=r.d[states],q=r.q[states],p=r.p[states])
        shutil.copyfile(r.folder/'checksums.json',case/'original-checksums.json')
        archive_source_snapshot(r.folder,case/'source.tar.gz')
        print(name,results[name]['seconds'],results[name]['final'][1],flush=True)
    a,b,c=[runs[k] for k in ('default','half_dt','quarter_dt')]
    ab=np.abs(a.d-b.d[::2]);bc=np.abs(b.d[::2]-c.d[::4])
    report=dict(description='Tero sigmoid equations on our London fine mesh. All food vertices are exact. This is a numerical sensitivity study, not biological calibration or an exact Tokyo reproduction.',generator_sha256=sha256_file(Path(__file__)),metrics_source_sha256=sha256_file(ROOT/'desktop/mesh_data.py'),runs=results,
        refinement=dict(forcing='Same mesh, initial D and food pairs at the same physical model times; switching interval held at .05.',max_transient_D_difference_dt_half=float(ab.max()),max_transient_D_difference_half_quarter=float(bc.max()),final_D_max_difference_dt_half=float(ab[-1].max()),final_D_max_difference_half_quarter=float(bc[-1].max()),transient_ratio=float(ab.max()/bc.max())),
        interpretation='Thresholded length/topology can change discontinuously. Mesh refinement changes candidate routes and initial degrees of freedom. No seed-independent optimum or general convergence claim. Single-break survival is our length-weighted one-break connectivity proxy, not the original paper statistic.')
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    write_report(report,args.output)
    assets=ROOT/'docs/assets';historical_figures=args.output/'figures';historical_figures.mkdir(exist_ok=True);fig=Figure(figsize=(12,8),dpi=160,layout='constrained',facecolor='white')
    for axis,target in zip(fig.subplots(2,2).flat,(0,3,10,30)):
        idx=int(np.argmin(abs(a.times-target)));draw_tubes(axis,a,idx);m=mesh_metrics(a,idx)
        axis.set_title(f"t = {a.times[idx]:g} · {m['largest_food_component']}/46 connected · {m['length_km']:.1f} km",fontsize=10,loc='left')
    fig.suptitle('London · flow-driven tube adaptation on a fine spatial mesh',fontsize=14)
    fig.supxlabel('γ = 1.8 · I₀ = 2 · seed 42 · D ≥ 10⁻⁴ · fixed width ∝ D¼ · model time, not hours\nTfL coordinates · © OpenStreetMap contributors',fontsize=8)
    for extension in ('png','svg'):save_figure(fig,historical_figures/f'euler-tube-evolution.{extension}')
    snapshot=snapshot_figure(a,len(a.times)-1,names=False)
    for extension in ('png','svg'):save_figure(snapshot,historical_figures/f'euler-tube-network.{extension}')
    # Parameter effects use measured final-state values at a common explicit cutoff.
    fig2=Figure(figsize=(11,4),dpi=160,layout='constrained');axes=fig2.subplots(1,3);names=list(results)
    for axis,key,label in zip(axes,('length_km','mean_route_direct_ratio','single_break_survival'),('Retained length (km)','Mean route / direct distance','One-break survival proxy')):
        values=[results[name]['final'][1][key] for name in names];axis.barh(names,[np.nan if v is None else v for v in values],color='#367e68');axis.set_xlabel(label,fontsize=8);axis.tick_params(labelsize=8);axis.spines[['top','right']].set_visible(False)
    fig2.suptitle('Euler baseline sensitivity · D ≥ 10⁻⁴ · exploratory London scenario',fontsize=12)
    fig2.savefig(assets/'tube-sensitivity.png',dpi=180)
    print('Recorded study:',args.output,flush=True)


def save_figure(figure,path):
    figure.savefig(path,dpi=180)
    if path.suffix=='.svg':path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


def write_report(report,folder):
    rows=[]
    for name,case in report['runs'].items():
        s=case['settings'];m=case['final'][1]
        rows.append(f"| {name} | {s['current']:g} | {s['gamma']:g} | {s['dt']:g} | {s['spacing']:g} | {s['seed']} | {m['largest_food_component']}/46 | {m['length_km']:.3f} | {m['mean_route_direct_ratio'] if m['mean_route_direct_ratio'] is None else round(m['mean_route_direct_ratio'],4)} | {m['single_break_survival']:.4f} | {m['worst_break_connected_pair_fraction']:.4f} |")
    default=report['runs']['default'];refinement=report['refinement']
    text=f'''# Fine-mesh tube study

Measured numerical sensitivity of the Tero sigmoid model on real London food coordinates. This is mesh adaptation, not biological expanding-front growth or an exact Tokyo reproduction. The default has {default['nodes']} vertices and {default['edges']} candidate segments, including 46 exact food vertices.

## Final-state measurements

D ≥ 10⁻⁴; duration 30; initial D = 0.5 ± 10%; forcing switches every 0.05 model units. River cost is 2 km equivalent only in `river_cost`; all other cases use zero. Cases otherwise differ from the default in the listed parameter. Seed changes mesh, initial values and forcing together.

| Case | I₀ | γ | Δt | Mesh km | Seed | Foods connected | Length km | Mean route/direct | One-break survival | Worst-break pair access |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

One-break survival assumes a single break uniform along retained length and asks whether all foods remain connected. It is not the paper's fault-tolerance statistic. Worst-break pair access is the fraction of all food pairs still connected under the most damaging single-segment removal; adding a useless dangling branch cannot improve it. Critical bridge length and expected post-break pair access are also in validation.json. Mean route/direct averages all 1,035 food-pair ratios, without silently excluding unreachable pairs. Physical length is distinct from resistance cost.

## Numerical evidence and limitations

Default maximum conservation residual: {default['max_conservation']:.5e}; maximum backward error: {default['max_backward_error']:.5e}; minimum scaled reciprocal-condition estimate: {default['min_scaled_rcond_estimate']:.5e}. The Hager-style diagnostic is an estimate, not a certified condition bound. Independent fixtures check sparse versus dense and NumPy pressures, analytic circuit flows, scalar dynamics, energy/work and Euler recurrence.

Refinement holds the exact graph, initial D and forcing fixed at aligned model times. Maximum transient D differences: {refinement['max_transient_D_difference_dt_half']:.6g} for Δt 0.05 → 0.025, and {refinement['max_transient_D_difference_half_quarter']:.6g} for 0.025 → 0.0125; ratio {refinement['transient_ratio']:.4g}. Final maximum differences: {refinement['final_D_max_difference_dt_half']:.6g} and {refinement['final_D_max_difference_half_quarter']:.6g}. Shrinking differences are consistent with the first-order method in this test, but substantive final geometry differences remain. These are finite-reference comparisons, not errors against an exact London solution. Thresholded topology can change discontinuously.

The JSON records every case at cutoffs 10⁻⁵, 10⁻⁴ and 10⁻³. Mesh refinement changes geometry and the number of initial values; it is not just another time step. Three seeds do not establish statistical reliability. No calibrated biological units, measured OD demand, tunnel mechanics, service capacity, optimality or railway feasibility is demonstrated.

## Reproduce and audit

`replay/<case>/` includes exact input graph/initial/forcing CSVs, a compressed scenario with source/software hashes, four numerical D/Q/P snapshots and original file checksums. Full dynamic runs remain local in ignored `results/mesh_runs/`. The compact public archive is a replay record, not itself a dynamic run folder.

```sh
.venv/bin/python analysis/replay_mesh_case.py results/mesh_validation/replay/default
.venv/bin/python analysis/run_mesh_validation.py --output results/another-mesh-study
```

Replay solves the frozen graph without retriangulating, validates every dynamic state, compares snapshots with rtol 2×10⁻⁷ / atol 2×10⁻⁸, and reports byte identity where the software/platform match. The default replay on the development Mac was byte-identical with zero snapshot difference. Cross-platform results must be assessed numerically. Generator/metric source hashes are recorded in validation.json. Use `--refresh` only when the referenced full local runs remain available; it revalidates them and refreshes measurements/figures without rerunning the engine.

Definitions and scope: [TUBE_EXPERIMENT.md](../../docs/TUBE_EXPERIMENT.md). [Primary source](https://doi.org/10.1126/science.1177894). TfL coordinates · © OpenStreetMap contributors · [data terms](../../data/london/README.md).
'''
    (folder/'REPORT.md').write_text(text)

if __name__=='__main__':main()
