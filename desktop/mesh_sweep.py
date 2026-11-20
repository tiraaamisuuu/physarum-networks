"""Paired parameter sweeps with complete per-run records and incremental summaries."""
import copy
import csv
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import uuid
import numpy as np
try:
    from .mesh_data import ROOT,validate_mesh_settings,build_mesh,run_mesh_experiment,mesh_metrics,mesh_raw_bytes,solver_extrema
except ImportError:
    from mesh_data import ROOT,validate_mesh_settings,build_mesh,run_mesh_experiment,mesh_metrics,mesh_raw_bytes,solver_extrema

PARAMETERS={'gamma':'Response γ','current':'Flow I₀','spacing':'Mesh spacing (km)','river_penalty':'River cost (km)','dt':'Time step Δt'}


def sweep_plan(settings,parameter,values,seeds):
    if parameter not in PARAMETERS:raise ValueError('Choose gamma, current, spacing, river_penalty or dt.')
    if not 2<=len(values)<=8 or len(set(values))!=len(values):raise ValueError('Choose 2–8 distinct parameter values.')
    if not 1<=len(seeds)<=8 or len(set(seeds))!=len(seeds):raise ValueError('Choose 1–8 distinct random seeds.')
    if len(values)*len(seeds)>24:raise ValueError('A sweep supports at most 24 experiments.')
    cases=[]
    for value in values:
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):raise ValueError('Parameter values must be finite numbers.')
        for seed in seeds:
            case={**settings,parameter:value,'seed':seed};validate_mesh_settings(case);cases.append(case)
    return cases


def run_sweep(scene,settings,parameter,values,seeds,cutoff=1e-4,root=None,cancel=None,progress=None):
    cases=sweep_plan(settings,parameter,values,seeds)
    if not math.isfinite(cutoff) or cutoff<=0:raise ValueError('Sweep cutoff must be finite and positive.')
    # Bound total raw storage before launching a queue; there is no state subsampling in records.
    estimate=0
    for case in cases:
        if cancel is not None and cancel.is_set():raise ValueError('Sweep cancelled before initialization.')
        mesh=build_mesh(scene,case)
        estimate+=mesh_raw_bytes(mesh,case)
    if estimate>2_000_000_000:raise ValueError('Sweep would record over 2 GB. Reduce cases, duration or mesh resolution.')
    folder=Path(root or ROOT/'results/mesh_sweeps')/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]);folder.mkdir(parents=True)
    plan=dict(schema_version=2,model='Tero_2010_sigmoid_mesh_v1',scene=copy.deepcopy(scene),base_settings=settings,parameter=parameter,values=values,seeds=seeds,cutoff=cutoff,cases=cases,estimated_raw_bytes=estimate,
        interpretation='One-parameter contrasts paired by seed. Seed changes mesh, initial D and demand sequence together. Report individual runs; a small seed sample does not establish statistical reliability.')
    (folder/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');rows=[]
    fields=['case','parameter','value','seed','cutoff','integrator','gamma','current','dt','spacing','river_penalty','duration','largest_food_component','food_count','length_km','mean_route_direct_ratio','single_break_survival','critical_bridge_length_km','expected_connected_pair_fraction_after_break','worst_break_connected_pair_fraction','max_conservation','max_backward_error','min_scaled_rcond_estimate','run_folder']
    try:
        with (folder/'summary.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();stream.flush()
            for i,case in enumerate(cases):
                if cancel is not None and cancel.is_set():raise ValueError('Sweep cancelled; completed cases and partial outputs are retained.')
                r=run_mesh_experiment(scene,case,root=folder/'runs',cancel=cancel);m=mesh_metrics(r,len(r.times)-1,cutoff,True)
                row=dict(case=i,parameter=parameter,value=case[parameter],seed=case['seed'],cutoff=cutoff,**{key:case[key] for key in ('gamma','current','dt','spacing','river_penalty','duration')},largest_food_component=m['largest_food_component'],food_count=r.food_count,length_km=m['length_km'],mean_route_direct_ratio=m['mean_route_direct_ratio'],single_break_survival=m['single_break_survival'],max_conservation=float(r.diagnostics[:,4].max()),max_backward_error=float(r.diagnostics[:,5].max()),min_scaled_rcond_estimate=float(r.diagnostics[:,6].min()),run_folder=str(r.folder.resolve()))
                row.update({key:m[key] for key in ('critical_bridge_length_km','expected_connected_pair_fraction_after_break','worst_break_connected_pair_fraction')})
                row.update(solver_extrema(r));row['integrator']=case.get('integrator','euler')
                rows.append(row);writer.writerow(row);stream.flush()
                (folder/'summary.json').write_text(json.dumps(dict(plan=plan,rows=rows,complete=len(rows)==len(cases)),indent=2)+'\n')
                if progress:progress(i+1,len(cases),copy.deepcopy(row))
        return dict(folder=str(folder.resolve()),plan=plan,rows=rows)
    except Exception as error:
        (folder/'failure.txt').write_text(str(error));raise ValueError(f'{error}\nSweep record: {folder}') from error


def load_sweep(folder):
    """Read the study index. Individual dynamic records are revalidated on inspection."""
    folder=Path(folder).resolve();plan=json.loads((folder/'plan.json').read_text());summary=json.loads((folder/'summary.json').read_text())
    if plan.get('schema_version') not in (1,2) or plan.get('model')!='Tero_2010_sigmoid_mesh_v1' or summary.get('plan')!=plan:raise ValueError('Study plan and summary disagree.')
    try:
        from .spatial_data import validate_scene,is_food
    except ImportError:from spatial_data import validate_scene,is_food
    validate_scene(plan['scene']);cases=sweep_plan(plan['base_settings'],plan['parameter'],plan['values'],plan['seeds'])
    if plan['cases']!=cases or not math.isfinite(plan['cutoff']) or plan['cutoff']<=0:raise ValueError('Invalid study plan.')
    rows=copy.deepcopy(summary['rows'])
    if not 1<=len(rows)<=len(cases) or summary['complete']!=(len(rows)==len(cases)):raise ValueError('Invalid completed-case count.')
    for i,row in enumerate(rows):
        case=cases[i]
        if row['case']!=i or row['parameter']!=plan['parameter'] or row['seed']!=case['seed'] or row['value']!=case[plan['parameter']]:raise ValueError('Study result does not match its planned case.')
        if not 2<=row['food_count']<=80 or not 1<=row['largest_food_component']<=row['food_count']:raise ValueError('Invalid food count in study summary.')
        if row['food_count']!=sum(is_food(n) for n in plan['scene']['nodes']):raise ValueError('Study food count disagrees with its scene.')
        for key in ('gamma','current','dt','spacing','river_penalty','duration'):
            if key in row and row[key]!=case[key]:raise ValueError('Study row settings disagree with its planned case.')
        for key in ('length_km','max_conservation','max_backward_error','min_scaled_rcond_estimate'):
            if not math.isfinite(row[key]) or row[key]<0:raise ValueError('Invalid study summary number.')
        if row['mean_route_direct_ratio'] is not None and (not math.isfinite(row['mean_route_direct_ratio']) or row['mean_route_direct_ratio']<1-1e-10):raise ValueError('Invalid route/direct ratio.')
        if (row['largest_food_component']==row['food_count'])!=(row['mean_route_direct_ratio'] is not None):raise ValueError('Route availability disagrees with food connectivity.')
        for key in ('single_break_survival','expected_connected_pair_fraction_after_break','worst_break_connected_pair_fraction'):
            if key in row and (not math.isfinite(row[key]) or not 0<=row[key]<=1):raise ValueError('Invalid break accessibility fraction.')
        if 'cutoff' in row and row['cutoff']!=plan['cutoff']:raise ValueError('Study cutoff differs between plan and result.')
        if 'integrator' in row and row['integrator']!=case.get('integrator','euler'):raise ValueError('Study integration method disagrees with its planned case.')
        row['cutoff']=plan['cutoff']
        # Resolve by saved directory name so a whole study can be moved between machines.
        run_folder=folder/'runs'/Path(row['run_folder']).name
        if not (run_folder/'scenario.json').is_file():raise ValueError(f'Missing dynamic run: {run_folder}')
        row['run_folder']=str(run_folder)
    return dict(folder=str(folder),plan=plan,rows=rows,complete=summary['complete'])
