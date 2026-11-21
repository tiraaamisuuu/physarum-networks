"""Explicit comparison conditions and final-state measurements for validated runs."""
import csv
import json
from pathlib import Path
import shutil
import numpy as np
try:
    from .experiment_catalog import record_key,scenario_key,validate_note
    from .mesh_data import mesh_metrics,effective_mesh_settings,compare_mesh_trajectories,archive_source_snapshot
except ImportError:
    from experiment_catalog import record_key,scenario_key,validate_note
    from mesh_data import mesh_metrics,effective_mesh_settings,compare_mesh_trajectories,archive_source_snapshot

PARAMETERS={'integrator':'Integration method','gamma':'Response γ','current':'Injected flow I₀','seed':'Random seed','spacing':'Mesh spacing (km)','dt':'Time step Δt','duration':'Duration','switch_interval':'Demand interval','river_penalty':'River cost (km)','initial_conductivity':'Initial conductivity','initial_noise':'Initial variation','demand_mode':'Forcing task','source_id':'Fixed start','sink_id':'Fixed target'}
METRICS=[('largest_food_component','Foods in largest component','foods'),('length_km','Retained physical length','km'),('mean_route_direct_ratio','Mean route / direct distance','ratio'),('single_break_survival','One-break survival proxy','fraction'),('worst_break_connected_pair_fraction','Worst-break connected pairs','fraction')]


def comparison_data(a,b,cutoff):
    sa,sb=effective_mesh_settings(a.settings),effective_mesh_settings(b.settings)
    food=lambda r:{n['key']:(n['x'],n['y'],n['kind']) for n in r.mesh['nodes'][:r.food_count]}
    same_foods=food(a)==food(b)
    coordinate=lambda r:'local_km' if r.scene['geography'].get('coordinate_system')=='local_km' else 'EPSG:27700 / km'
    # Local arenas have no shared geographic origin beyond their declared bounds.
    same_space=coordinate(a)==coordinate(b) and (coordinate(a)!='local_km' or a.scene['geography']['design_bounds_km']==b.scene['geography']['design_bounds_km'])
    geometry=lambda r:([(n['key'],n['kind'],n['x'],n['y']) for n in r.mesh['nodes']],[(e['from'],e['to'],e['distance_km'],e['length']) for e in r.mesh['edges']])
    same_geometry=same_space and geometry(a)==geometry(b)
    same_initial=same_geometry and np.array_equal(a.d[0],b.d[0])
    coarse,fine=(a,b) if a.settings['dt']>=b.settings['dt'] else (b,a)
    ratio=round(coarse.settings['dt']/fine.settings['dt'])
    aligned=ratio>=1 and abs(ratio*fine.settings['dt']-coarse.settings['dt'])<1e-12 and len(fine.times)==ratio*(len(coarse.times)-1)+1
    if aligned:aligned=np.allclose(coarse.times,fine.times[::ratio],rtol=0,atol=1e-10)
    same_schedule=bool(same_foods and aligned and np.array_equal(fine.pairs,coarse.pairs[np.arange(len(fine.times))//ratio]) and [n['key'] for n in a.mesh['nodes'][:a.food_count]]==[n['key'] for n in b.mesh['nodes'][:b.food_count]])
    same_current=sa['current']==sb['current'];same_forcing=same_schedule and same_current
    changes=[]
    for key,label in PARAMETERS.items():
        if key in ('source_id','sink_id') and sa['demand_mode']!='fixed_pair' and sb['demand_mode']!='fixed_pair':continue
        if sa[key]!=sb[key]:changes.append(dict(key=key,label=label,reference=sa[key],current=sb[key]))
    if a.scene['barriers']!=b.scene['barriers']:changes.append(dict(key='barriers',label='Blocked-area geometry',reference=a.scene['barriers'],current=b.scene['barriers']))
    weights_a=a.scene.get('weighted_demand',{}).get('pairs',[]);weights_b=b.scene.get('weighted_demand',{}).get('pairs',[])
    if 'weighted_pairs' in (sa['demand_mode'],sb['demand_mode']) and weights_a!=weights_b:changes.append(dict(key='weighted_demand',label='Relative pair weights',reference=weights_a,current=weights_b))
    if not same_foods:changes.append(dict(key='food_sites',label='Food sites',reference=f'{a.food_count} sites',current=f'{b.food_count} sites; IDs or coordinates differ'))
    metrics_a,metrics_b=[mesh_metrics(r,len(r.times)-1,cutoff,True) for r in (a,b)]
    rows=[]
    for key,label,unit in METRICS:
        av,bv=metrics_a[key],metrics_b[key]
        rows.append(dict(key=key,label=label,unit=unit,reference=av,current=bv,delta=bv-av if same_space and same_foods and av is not None and bv is not None else None))
    numerical=compare_mesh_trajectories(a,b)
    if not same_space:summary='Different coordinate contexts. Maps use independent extents and measurement deltas are withheld.'
    elif not same_foods:summary='Food sites differ. Connectivity and route measurements concern different food populations; deltas are withheld.'
    elif same_geometry and same_initial and same_schedule:summary='Candidate geometry, initial conductivities and the complete held food-pair schedule match. Review the changed controls below before interpreting differences.'
    else:summary='These runs share food sites, but geometry, initialization or forcing differ. The comparison describes combined changes.'
    return dict(schema_version=1,cutoff=cutoff,reference=dict(folder=str(a.folder.resolve()),scenario_sha256=record_key(a),food_count=a.food_count,final_time=float(a.times[-1]),settings=sa),current=dict(folder=str(b.folder.resolve()),scenario_sha256=record_key(b),food_count=b.food_count,final_time=float(b.times[-1]),settings=sb),conditions=dict(same_coordinate_context=same_space,same_food_sites=same_foods,same_candidate_geometry=same_geometry,same_initial_conductivities=bool(same_initial),same_food_pair_schedule=same_schedule,same_injected_current=same_current,same_held_forcing=same_forcing),changes=changes,measurements=rows,summary=summary,numerical=numerical,interpretation='Final recorded states at one shared display cutoff. Deltas are current minus reference, not improvement scores. Measurements do not establish biological fidelity or railway feasibility.')


def export_comparison(a,b,data,figure,folder,notes=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    for label,run in (('reference',a),('current',b)):
        if scenario_key(run.folder)!=record_key(run):raise ValueError('A recorded scenario changed after opening. Reopen and revalidate before exporting.')
        shutil.copyfile(run.folder/'scenario.json',folder/f'{label}-scenario.json');archive_source_snapshot(run.folder,folder/f'{label}-source.tar.gz')
    payload=dict(data)
    payload['user_annotations']={key:validate_note(value) for key,value in (notes or {}).items()}
    (folder/'comparison.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
    with (folder/'measurements.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['key','label','unit','reference','current','delta']);writer.writeheader();writer.writerows(data['measurements'])
    figure.canvas.draw();figure.canvas.draw()
    for ext in ('png','svg'):figure.savefig(folder/f'comparison.{ext}',dpi=180)
    (folder/'README.txt').write_text('Comparison figure/data extract, not a complete dynamic run.\nOriginal full records are identified in comparison.json.\nSource archives contain indexed code only. Notes are user annotations, separate from numerical evidence.\n')
