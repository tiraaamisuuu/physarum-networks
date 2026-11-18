"""Quantitative tube figures and snapshot exports, independent of Qt."""
import csv
import json
from pathlib import Path
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
try:
    from .mesh_data import DEFAULT_CUTOFF, mesh_metrics
except ImportError:
    from mesh_data import DEFAULT_CUTOFF, mesh_metrics

INK='#263d38'
FOOD='#13856e'


def tube_widths(d):
    """Fixed display scale: 1.2 pt at D=.5; r ∝ D^(1/4). No smoothing."""
    return 1.2*(np.asarray(d)/.5)**.25


def draw_tubes(axis,run,index,cutoff=DEFAULT_CUTOFF,names=False,background=False):
    xy=np.array([[n['x'],n['y']] for n in run.mesh['nodes']])
    endpoints=np.array([[e['from'],e['to']] for e in run.mesh['edges']])
    segments=xy[endpoints];keep=run.d[index]>=cutoff
    axis.set_facecolor('#fafbf8')
    river=LineCollection([way['xy_km'] for way in run.scene['geography']['river']],colors='#83b3c4',linewidths=1.3,alpha=.8,zorder=1)
    axis.add_collection(river)
    for x0,y0,x1,y1 in run.scene['barriers']:
        axis.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor='#c89686',edgecolor='#a76351',hatch='//',alpha=.3,zorder=2))
    if background:axis.add_collection(LineCollection(segments,colors='#dce1dd',linewidths=.25,zorder=2))
    links=LineCollection(segments[keep],colors=INK,linewidths=tube_widths(run.d[index,keep]),zorder=3)
    axis.add_collection(links)
    f=run.food_count
    axis.scatter(*xy[:f].T,s=22,facecolors='#fafbf8',edgecolors=FOOD,linewidths=1,zorder=5)
    pair=run.pairs[index]
    axis.scatter(*xy[pair].T,s=44,c=['#196fad','#cf7639'],edgecolors='white',linewidths=.8,zorder=6)
    if names:
        for n in run.mesh['nodes'][:f]:axis.annotate(n['name'],(n['x'],n['y']),xytext=(4,4),textcoords='offset points',fontsize=6,zorder=7)
    axis.set_xlim(xy[:,0].min()-.2,xy[:,0].max()+.2);axis.set_ylim(xy[:,1].min()-.2,xy[:,1].max()+.2)
    axis.set_aspect('equal');axis.tick_params(labelsize=8)
    axis.set_xlabel('British National Grid easting (km)',fontsize=8);axis.set_ylabel('Northing (km)',fontsize=8)
    axis.spines[['top','right']].set_visible(False)
    return links


def snapshot_figure(run,index,cutoff=DEFAULT_CUTOFF,names=False):
    figure=Figure(figsize=(11,7),dpi=160,layout='constrained',facecolor='white')
    axis=figure.add_subplot();draw_tubes(axis,run,index,cutoff,names)
    metrics=mesh_metrics(run,index,cutoff,True)
    axis.set_title(f"London · adaptive tube network · t = {run.times[index]:g}",loc='left',fontsize=12,pad=18)
    figure.suptitle(f"γ = {run.settings['gamma']:g}   I₀ = {run.settings['current']:g}   Δt = {run.settings['dt']:g}   seed = {run.settings['seed']}   mesh = {run.settings['spacing']:g} km",fontsize=9)
    axis.text(.01,.01,f"{metrics['largest_food_component']}/{run.food_count} foods in largest component · retained length {metrics['length_km']:.2f} km\nD ≥ {cutoff:g}; width ∝ D¼ (1.2 pt at D = 0.5). Blue/orange: current source/sink.\nTfL coordinates · © OpenStreetMap contributors · model time, not biological hours",transform=axis.transAxes,fontsize=7,color='#40514b',va='bottom',bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
    return figure


def export_snapshot(run,index,folder,cutoff=DEFAULT_CUTOFF,names=False):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    metrics=mesh_metrics(run,index,cutoff,True)
    record=dict(model='Tero_2010_sigmoid_mesh_v1',run_folder=str(run.folder.resolve()),state=index,time=float(run.times[index]),settings=run.settings,metrics=metrics,
        interpretation='Cutoff defines this measured/displayed graph only; all numerical D are unchanged. Single-break survival assumes one break uniformly along retained physical length; it is not the paper’s fault-tolerance statistic. Terminal MST is a reference, not a Steiner lower bound.')
    (folder/'snapshot.json').write_text(json.dumps(record,indent=2)+'\n')
    with (folder/'tubes.csv').open('w',newline='') as stream:
        w=csv.writer(stream);w.writerow(['edge','from','to','distance_km','effective_length','D','Q','p_from','p_to','retained'])
        for k,e in enumerate(run.mesh['edges']):w.writerow([k,e['from'],e['to'],e['distance_km'],e['length'],run.d[index,k],run.q[index,k],run.p[index,e['from']],run.p[index,e['to']],int(run.d[index,k]>=cutoff)])
    with (folder/'nodes.csv').open('w',newline='') as stream:
        w=csv.writer(stream);w.writerow(['node','name','food','easting_km','northing_km','pressure'])
        for i,n in enumerate(run.mesh['nodes']):w.writerow([i,n['name'],int(i<run.food_count),n['x'],n['y'],run.p[index,i]])
    fig=snapshot_figure(run,index,cutoff,names)
    for extension in ('svg','png'):fig.savefig(folder/f'network.{extension}',dpi=200)
    return record
