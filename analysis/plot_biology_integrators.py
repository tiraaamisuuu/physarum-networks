#!/usr/bin/env python3
"""Frozen-reference integration plots and explicit geometric diagnostics."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gzip
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
import numpy as np
from desktop.biology_data import ROOT,sha
from desktop.biology_metrics import vein_metrics
from analysis.plot_biology import colony
BASE=ROOT/'results/biology_integration';ASSETS=ROOT/'docs/assets'

def read_gzip_csv(path):
    with gzip.open(path,'rt') as stream:
        names=stream.readline().strip().split(',');return np.loadtxt(stream,delimiter=',',dtype=[(name,float) for name in names],ndmin=1)

def frozen(name):
    folder=BASE/'replay'/name;nodes=np.loadtxt(folder/'nodes.csv',delimiter=',',skiprows=1);edges=np.loadtxt(folder/'edges.csv',delimiter=',',skiprows=1);tri=np.loadtxt(folder/'triangles.csv',delimiter=',',skiprows=1,dtype=int);ref=np.load(folder/'reference.npz');return nodes,edges,tri,ref,read_gzip_csv(folder/'history.csv.gz'),None

def save(fig,name):
    for extension in ('png','svg'):fig.savefig(ASSETS/(name+'.'+extension),dpi=180)
    p=ASSETS/(name+'.svg');p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n');plt.close(fig)

def main():
    report=json.loads((BASE/'validation.json').read_text());cases=report['cases'];names=['midpoint_coarse','midpoint','midpoint_half','midpoint_fine']
    if not all(n in cases for n in ['legacy']+names):raise ValueError('Complete all five integration cases before generating the report figures.')
    for name,item in cases.items():
        n,e,tri,ref,history,_=frozen(name);item['final_vein_graph_D1']=vein_metrics(n[:,1:3],e[:,1:],ref['d'][-1],n[:,4],item['settings']['arena'])
        probe=read_gzip_csv(BASE/'replay'/name/'probe.csv.gz');use=probe['time']>=1200;c=probe['c'][use];t=probe['time'][use];peaks=np.flatnonzero((c[1:-1]>c[:-2])&(c[1:-1]>c[2:]))+1;item['late_mean_sampled_peak_period']=float(np.diff(t[peaks]).mean()) if len(peaks)>1 else None
        fine=np.load(BASE/'replay/midpoint_fine/reference.npz');item['final_D1_mask_differences_from_finest']=int(np.count_nonzero((ref['d'][-1]>=1)!=(fine['d'][-1]>=1)));item['relative_mean_volume_difference_from_finest']=item['last_80_time_mean_volume']/cases['midpoint_fine']['last_80_time_mean_volume']-1
    (BASE/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,'svg.hashsalt':'physarum-biological-integration-v1'})
    order=np.genfromtxt(BASE/'smooth-order.csv',delimiter=',',names=True,dtype=None,encoding='utf-8');fig,axs=plt.subplots(2,2,figsize=(12,7.4),layout='constrained')
    for method,color,label in [('legacy','#ac783b','Legacy split'),('midpoint','#356b50','Midpoint / CN')]:
        a=order[order['integrator']==method];axs[0,0].loglog(a['dt'],a['scaled_error'],'o-',color=color,label=label,lw=1.3,ms=4)
    axs[0,0].set(title='A · Small-case integration error',xlabel='Time step (refinement →)',ylabel='Scaled state error');axs[0,0].invert_xaxis();ticks=np.unique(order['dt']);axs[0,0].set_xticks(ticks,[f'{h:g}' for h in ticks]);axs[0,0].xaxis.set_minor_locator(NullLocator());axs[0,0].legend(frameon=False,fontsize=8)
    steps=np.array([cases[n]['settings']['dt'] for n in names]);vol=np.array([cases[n]['last_80_time_mean_volume'] for n in names]);length=np.array([cases[n]['last_80_time_mean_retained_length_D1'] for n in names])
    for ax,values,key,title,label in [(axs[0,1],vol,'last_80_time_mean_volume','B · Full-corridor volume proxy','Mean Σ ℓ√D (model units)'),(axs[1,0],length,'last_80_time_mean_retained_length_D1','C · Full-corridor retained veins','Mean retained length · D ≥ 1')]:
        ax.semilogx(steps,values,'o-',color='#356b50',lw=1.4,ms=4,label='Midpoint / CN');ax.scatter([.02],[cases['legacy'][key]],marker='s',s=32,color='#ac783b',label='Legacy at Δt = 0.02');ax.set(title=title,xlabel='Time step (refinement →)',ylabel=label);ax.invert_xaxis();ax.set_xticks(steps,[f'{h:g}' for h in steps]);ax.xaxis.set_minor_locator(NullLocator());ax.legend(frameon=False,fontsize=8)
    g=read_gzip_csv(BASE/'replay/midpoint/global.csv.gz');use=g['time']>=1272;axs[1,1].plot(g['time'][use],g['vein_volume'][use],lw=1.2,color='#356b50');axs[1,1].set(title='D · Fast changes between spatial snapshots',xlabel='Model time · every integration step',ylabel='Volume proxy Σ ℓ√D');sparse=(g['time']>=1272)&(np.isclose(g['time']%8,0,atol=1e-9));axs[1,1].scatter(g['time'][sparse],g['vein_volume'][sparse],s=28,color='#ac783b',zorder=4,label='Spatial snapshot times');axs[1,1].legend(frameon=False,fontsize=8)
    for ax in axs.ravel():ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.16);ax.tick_params(labelsize=8)
    fig.suptitle('Coupled growth · numerical refinement and full-rate measurements',fontsize=14,x=.035,ha='left');save(fig,'biology-integration')
    data=frozen('midpoint');fig,axs=plt.subplots(2,2,figsize=(12,6.3),layout='constrained')
    for ax,i in zip(axs.ravel(),[0,1,3,8]):colony(ax,data,i,f"Midpoint / CN  ·  t = {data[3]['times'][i]:g}");ax.set_xlabel('Model length');ax.set_ylabel('Model length')
    seed=data[0][data[0][:,4]>0,1:3].mean(axis=0);axs[0,0].scatter(*seed,s=24,facecolors='none',edgecolors='#f1dc93',lw=.9);axs[0,0].annotate('Initial patch',seed,xytext=(-55,20),textcoords='offset points',fontsize=8,color='#f1dc93',arrowprops=dict(arrowstyle='-',color='#f1dc93',lw=.7))
    fig.suptitle('Exploratory growth · cooperative calcium / fast-front variant',fontsize=14,x=.035,ha='left');fig.supxlabel('Actual C++ fields · D ≥ 1, width ∝ D¼ · body is a model proxy · no food-response model or biological calibration',fontsize=9);save(fig,'biology-growth-midpoint')
    provenance=dict(generator_sha256=sha(__file__),metric_source_sha256=sha(ROOT/'desktop/biology_metrics.py'),validation_sha256=sha(BASE/'validation.json'),smooth_order_sha256=sha(BASE/'smooth-order.csv'),numpy=np.__version__,matplotlib=matplotlib.__version__,figures={name:sha(ASSETS/name) for name in ('biology-integration.png','biology-integration.svg','biology-growth-midpoint.png','biology-growth-midpoint.svg')})
    (ASSETS/'biology-integration.json').write_text(json.dumps(provenance,indent=2)+'\n')
if __name__=='__main__':main()
