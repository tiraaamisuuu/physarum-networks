#!/usr/bin/env python3
"""Recompute the default inoculum experiment and render its recorded fields."""
import argparse
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation,PillowWriter
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.collections import LineCollection
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from desktop.growth_data import DEFAULT_GROWTH,default_scene,run_growth_experiment,load_growth_run,sha256_file

COLOURS=['#101c24','#4f3525','#bc7a18','#f6d55b','#fff2b0']


def draw_arena(axis,run):
    axis.set_facecolor(COLOURS[0]);image=axis.imshow(run.trail[0],origin='lower',extent=run.extent,cmap=LinearSegmentedColormap.from_list('activity',COLOURS),vmin=0,vmax=15,interpolation='nearest')
    axis.add_collection(LineCollection([w['xy_km'] for w in run.scene['geography']['river']],colors='#6d9eb8',linewidths=.8,alpha=.6))
    xy=np.array([[n['x'],n['y']] for n in run.foods]);sites=axis.scatter(xy[:,0],xy[:,1],s=10,edgecolors=COLOURS[0],linewidths=.3)
    axis.set_xlim(run.extent[:2]);axis.set_ylim(run.extent[2:]);axis.set_aspect('equal');axis.set_axis_off()
    return image,sites


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path);parser.add_argument('--gif',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/assets/growth-evolution');args=parser.parse_args()
    run=load_growth_run(args.run) if args.run else run_growth_experiment(default_scene(),DEFAULT_GROWTH)
    indices=[int(np.abs(run.steps-tick).argmin()) for tick in (0,100,300,1600)]
    figure,axes=plt.subplots(2,2,figsize=(11,7.5),layout='constrained',facecolor=COLOURS[0])
    for axis,index in zip(axes.flat,indices):
        image,sites=draw_arena(axis,run);image.set_data(run.trail[index]);tick=run.steps[index]
        visited=(run.contacts>=0)&(run.contacts<=tick);active=run.activity[index]>0
        sites.set_facecolors(['#68bda7' if active[i] else '#dda64b' if flag else '#f1eee0' for i,flag in enumerate(visited)])
        axis.set_title(f'Update {tick} · {int(active.sum())}/{len(visited)} sites active nearby',loc='left',fontsize=10,color='white',pad=7)
    figure.suptitle('From one patch to an evolving network',fontsize=18,fontweight='bold',color='#fff2b0',x=.05,ha='left')
    figure.supxlabel('London station food layout · King’s Cross St Pancras start · C++ particle simulation\n'
        'Gold = trail (fixed 0–15). Green = nearby particles now; amber = previously visited, now empty nearby.\n'
        'Updates are not hours. TfL station data · © OpenStreetMap contributors.',fontsize=8,color='#d3dce0')
    args.output.parent.mkdir(parents=True,exist_ok=True);figure.savefig(args.output.with_suffix('.png'),dpi=180)
    summary=dict(model_version=run.model_version,settings=run.settings,frames=len(run.stats),shape=list(run.trail.shape),selected_updates=run.steps[indices].tolist(),
        final_live_particles=int(run.stats[-1,2]),peak_live_particles=int(run.stats[:,2].max()),visited_sites=int(run.stats[-1,3]),
        last_first_contact_update=int(run.contacts.max()),initial_live_particles=int(run.stats[0,2]),
        nearby_sites_final=int((run.activity[-1]>0).sum()),
        trail_sha256=sha256_file(run.folder/'output/trail.f32'),occupancy_sha256=sha256_file(run.folder/'output/occupied.u8'),
        contacts_sha256=sha256_file(run.folder/'output/food.csv'),stats_sha256=sha256_file(run.folder/'output/stats.csv'),
        software=json.loads((run.folder/'scenario.json').read_text())['software'],
        interpretation='Recorded particle trail, not Tero conductivity or an engineering rail alignment.')
    args.output.with_suffix('.json').write_text(json.dumps(summary,indent=2)+'\n')
    if args.gif:
        fig,axis=plt.subplots(figsize=(9,6),facecolor=COLOURS[0]);fig.subplots_adjust(left=.02,right=.98,top=.9,bottom=.13)
        image,sites=draw_arena(axis,run);title=axis.set_title('',color='#fff2b0',fontsize=12,loc='left',pad=12)
        fig.text(.04,.055,'Simulated colony activity · station food layout · fixed colour scale\n'
            'Green: particles nearby now; amber: previously visited, empty nearby. Neither proves connectivity.\nTfL data · © OpenStreetMap contributors.',fontsize=8,color='#d3dce0')
        stride=max(1,len(run.stats)//80);frames=list(range(0,len(run.stats),stride))
        if frames[-1]!=len(run.stats)-1:frames.append(len(run.stats)-1)
        def update(index):
            image.set_data(run.trail[index]);tick=run.steps[index];visited=(run.contacts>=0)&(run.contacts<=tick);active=run.activity[index]>0
            sites.set_facecolors(['#68bda7' if active[i] else '#dda64b' if flag else '#f1eee0' for i,flag in enumerate(visited)])
            title.set_text(f'London · update {tick} · {active.sum()}/{len(visited)} sites have nearby particles')
            return image,sites,title
        animation=FuncAnimation(fig,update,frames=frames,interval=125,blit=False)
        animation.save(args.output.with_suffix('.gif'),writer=PillowWriter(fps=8),dpi=100)
    print(f'Raw run: {run.folder}\nFigure: {args.output.with_suffix(".png")}\nLast first contact: update {run.contacts.max()}')


if __name__=='__main__':main()
