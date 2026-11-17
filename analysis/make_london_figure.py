#!/usr/bin/env python3
"""Run the frozen London example and render measured geographic snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop.spatial_data import DEFAULT_SETTINGS,default_scene,run_spatial_experiment,load_spatial_run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,help='Read an existing spatial run instead of computing the default.')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/assets/london-evolution')
    args=parser.parse_args()
    run=load_spatial_run(args.run) if args.run else run_spatial_experiment(ROOT/'build/physarum_run',default_scene(),DEFAULT_SETTINGS)
    indices=np.rint(np.linspace(0,len(run.times)-1,4)).astype(int)
    xy=np.array([[node['x'],node['y']] for node in run.scene['nodes']])
    segments=[xy[[edge['from'],edge['to']]] for edge in run.edges]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.spines.top':False,'axes.spines.right':False})
    figure,axes=plt.subplots(2,2,figsize=(11,7.3),layout='constrained',sharex=True,sharey=True)
    for axis,index in zip(axes.flat,indices):
        axis.add_collection(LineCollection([way['xy_km'] for way in run.scene['geography']['river']],colors='#7db5d0',linewidths=2.3,zorder=1))
        axis.add_collection(LineCollection(segments,colors='#cdd5d9',linewidths=.35,zorder=2))
        widths=3*np.sqrt(run.d[index]/.5);widths[run.d[index]<1e-10]=0
        axis.add_collection(LineCollection(segments,colors='#234857',linewidths=widths,alpha=.85,zorder=3))
        axis.scatter(xy[:,0],xy[:,1],s=9,facecolor='white',edgecolors='#234857',linewidths=.5,zorder=4)
        source,sink=run.sources[index],run.sinks[index]
        axis.scatter(xy[[source,sink],0],xy[[source,sink],1],s=28,c=['#087f8c','#c35b2d'],edgecolors='white',linewidths=.6,zorder=5)
        for i,node in enumerate(run.scene['nodes']):
            if node['name'] in ('Paddington','Stratford','Waterloo','Canary Wharf','Stockwell'):
                axis.annotate(node['name'],xy[i],xytext=(3,4),textcoords='offset points',fontsize=6.5,zorder=6)
        axis.set_xlim(xy[:,0].min()-1,xy[:,0].max()+1);axis.set_ylim(xy[:,1].min()-1,xy[:,1].max()+1)
        axis.set_aspect('equal');axis.grid(alpha=.13,lw=.4)
        axis.set_title(f't = {run.times[index]:.2f}  |  step {index}',loc='left',fontweight='bold',fontsize=10)
        axis.set_xlabel('Easting (km)');axis.set_ylabel('Northing (km)')
    figure.suptitle('London · adaptive connections between real station locations',fontsize=15,fontweight='bold',x=.055,ha='left')
    demand='Uniform synthetic station pairs' if run.settings['demand_mode']=='uniform_pairs' else 'Fixed station pair'
    figure.supxlabel(f'{demand} · seed {run.settings["seed"]} · assumed Thames penalty +{run.settings["river_penalty"]:g} km eq.\n'
        'Width ∝ √D, fixed scale; pale outlines retain candidate edges. Model time is arbitrary.\n'
        'TfL station data · © OpenStreetMap contributors · exploratory model, no transport feasibility claim.',fontsize=8)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for extension in ('.png','.svg'):figure.savefig(args.output.with_suffix(extension),dpi=190)
    svg=args.output.with_suffix('.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    summary={'settings':run.settings,'nodes':len(run.scene['nodes']),'edges':len(run.edges),'states':len(run.times),
        'crossing_candidates':sum(edge['river_crossing'] for edge in run.edges),'figure_steps':indices.tolist(),
        'max_conservation_residual':float(run.diagnostics[:,0].max()),'max_backward_error':float(run.diagnostics[:,1].max()),
        'min_scaled_rcond':float(run.diagnostics[:,2].min()),'final_D_range':[float(run.d[-1].min()),float(run.d[-1].max())],
        'history_sha256':hashlib.sha256((run.folder/'output/history.csv').read_bytes()).hexdigest(),
        'scenario_sha256':hashlib.sha256((run.folder/'scenario.json').read_bytes()).hexdigest(),
        'geography_sha256':hashlib.sha256((ROOT/'data/london/geography.json').read_bytes()).hexdigest(),
        'software':json.loads((run.folder/'scenario.json').read_text())['software'],
        'elevation_role':'context only; omitted from this figure','physical_validation':'No passenger demand or engineering validation.'}
    args.output.with_suffix('.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(f'Figure: {args.output.with_suffix(".png")}\nRaw local run: {run.folder}\nMaximum conservation residual: {summary["max_conservation_residual"]:.6g}')


if __name__=='__main__':main()
