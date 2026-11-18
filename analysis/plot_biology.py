#!/usr/bin/env python3
"""Publication-style figures from frozen growth records, without source photos."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gzip
import io
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
from desktop.biology_data import ROOT,geometry

BASE=ROOT/'results/biology_validation';ASSETS=ROOT/'docs/assets'
def case(name):
    p=BASE/'replay'/name;nodes=np.loadtxt(p/'nodes.csv',delimiter=',',skiprows=1);edges=np.loadtxt(p/'edges.csv',delimiter=',',skiprows=1);tri=np.loadtxt(p/'triangles.csv',delimiter=',',skiprows=1,dtype=int);ref=np.load(p/'reference.npz');history=np.genfromtxt(io.BytesIO(gzip.decompress((p/'history.csv.gz').read_bytes())),delimiter=',',names=True);probe=np.genfromtxt(io.BytesIO(gzip.decompress((p/'probe.csv.gz').read_bytes())),delimiter=',',names=True);return nodes,edges,tri,ref,history,probe

def colony(ax,data,index,title):
    nodes,edges,tri,ref,_,_=data;xy=nodes[:,1:3];w=ref['w'][index];d=ref['d'][index];ax.set_facecolor('#11241f');ax.tricontourf(*xy.T,tri,w,levels=[-1,.1,.9,1,max(1.1,float(w.max())+1)],colors=['#1d3027','#798b45','#657443','#344d32']);p,_=geometry('snake');p=np.vstack([p,p[0]]);ax.plot(*p.T,color='#b9c4a3',lw=.6);use=d>=1;ax.add_collection(LineCollection(xy[edges[use,1:3].astype(int)],colors='#f1dc93',linewidths=.5*d[use]**.25));ax.set_aspect('equal');ax.set(xlim=(-.5,40.5),ylim=(-.6,15.6));ax.tick_params(labelsize=7);ax.set_title(title,loc='left',fontsize=10,pad=8);ax.spines[['top','right']].set_visible(False)

def save(fig,name):
    ASSETS.mkdir(exist_ok=True);fig.savefig(ASSETS/(name+'.png'),dpi=180);fig.savefig(ASSETS/(name+'.svg'))
    path=ASSETS/(name+'.svg');path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n');plt.close(fig)

def main():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,'axes.titlesize':10,'svg.hashsalt':'physarum-biology-v1'})
    default=case('default');fig,axs=plt.subplots(2,2,figsize=(12,6.3),layout='constrained')
    for ax,i,label in zip(axs.ravel(),[0,1,3,8],['A · Inoculum','B · Advancing margin','C · Following the bends','D · Final accumulated footprint']):
        colony(ax,default,i,f"{label}  ·  t = {default[3]['times'][i]:g}")
        ax.set_xlabel('Model length');ax.set_ylabel('Model length')
    fig.suptitle('Exploratory growth · cooperative calcium / fast-front variant',fontsize=14,x=.035,ha='left');fig.supxlabel('Actual C++ fields · thin gold: D ≥ 1; width ∝ D¼ · body colour: w proxy, not microscopy · uncalibrated units',fontsize=9);save(fig,'biology-growth')
    results=json.loads((BASE/'validation.json').read_text())['cases'];fig,axs=plt.subplots(2,2,figsize=(12,7.2),layout='constrained');colors={'default':'#356b50','source_front':'#a87938','no_feedback':'#7a6789','printed_control':'#8f9892','half_dt':'#477ca1','finer_mesh':'#b76543'};labels={'default':'Cooperative / τ₂ = 2','source_front':'Source front timescale τ₂ = 20','no_feedback':'No front feedback k = 0','printed_control':'Printed Hill 1 control','half_dt':'Half time step Δt = 0.01','finer_mesh':'Finer mesh h = 0.4'}
    for name in ('default','source_front','no_feedback','printed_control'):
        data=case(name);h=data[4];axs[0,0].plot(h['time'],h['body_area']/350*100,color=colors[name],label=labels[name],lw=1.4,ls='--' if name in ('no_feedback','printed_control') else '-')
    axs[0,0].set(title='A · An advancing footprint does not establish veins',xlabel='Model time',ylabel='Occupied arena (%)');axs[0,0].legend(frameon=False,fontsize=7,loc='center right',bbox_to_anchor=(.98,.45))
    for name in ('default','printed_control'):
        p=case(name)[5];use=p['time']>=1272;axs[0,1].plot(p['time'][use],p['c'][use],label=labels[name],color=colors[name],lw=1.2)
    axs[0,1].set(title='B · Printed expression settles; cooperative variant cycles',xlabel='Model time · full-rate probe',ylabel='Calcium at inoculum');axs[0,1].legend(frameon=False,fontsize=7,loc='lower left',bbox_to_anchor=(0,.09))
    names=['default','half_dt','finer_mesh','no_feedback','printed_control'];values=[results[n]['retained_length_D1'] for n in names];axs[1,0].bar(np.arange(len(names)),values,color=[colors[n] for n in names],width=.62)
    axs[1,0].set_xticks(np.arange(len(names)),['Default','Half Δt','Finer h','k = 0','Hill 1']);axs[1,0].set(title='C · Vein geometry remains numerically sensitive',ylabel='Retained length · D ≥ 1 (model units)')
    for i,v in enumerate(values):axs[1,0].text(i,v+.8,f'{v:.2f}',ha='center',fontsize=8)
    p=default[5];use=p['time']>=1272;axs[1,1].plot(p['time'][use],p['q'][use],color='#aa783a',lw=1.1);axs[1,1].axhline(0,color='#6c766d',ls='--',lw=.7);axs[1,1].set(title='D · Signed internal flow reverses',xlabel='Model time · full-rate incident-edge probe',ylabel='Signed flow (model units)')
    for ax in axs.ravel():ax.spines[['top','right']].set_visible(False);ax.tick_params(labelsize=8);ax.grid(axis='y',alpha=.15)
    fig.suptitle('Growth-model controls · useful evidence, not biological validation',fontsize=14,x=.035,ha='left');save(fig,'biology-controls')
if __name__=='__main__':main()
