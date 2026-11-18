#!/usr/bin/env python3
"""Run explicit growth-model controls; preserve exact inputs and sampled fields.

No acceptance threshold for resemblance to microscopy is implied. These are
numerical/phenomenological checks of a named variant, not a paper replication.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import gzip
import io
import json
import tarfile
import numpy as np
from desktop.biology_data import ROOT,DEFAULT_BIOLOGY,run_biology,sha

def body_components(run,index):
    occupied=run['fields']['w'][index]>1;active=set(np.flatnonzero(occupied));adj=[[] for _ in occupied]
    for a,b,_,_ in run['edges']:
        a,b=int(a),int(b)
        if occupied[a] and occupied[b]:adj[a].append(b);adj[b].append(a)
    areas=[]
    while active:
        a=active.pop();stack=[a];area=run['mass'][a]
        while stack:
            for b in adj[stack.pop()]:
                if b in active:active.remove(b);stack.append(b);area+=run['mass'][b]
        areas.append(area)
    return len(areas),max(areas,default=0.)

def summarize(run):
    h=run['history'];p=run['probe'];late=p['time']>=run['settings']['duration']-80;c=p['c'][late];q=p['q'][late];peaks=np.flatnonzero((c[1:-1]>c[:-2])&(c[1:-1]>c[2:]))+1
    count,largest=body_components(run,-1);seed=run['inoculum'];xy=run['xy'];target=(xy[:,0]<=1)&(xy[:,1]>=10 if run['settings']['arena']=='snake' else True)
    reached=(run['fields']['w'][:,target]>1).any(axis=1);first=int(np.flatnonzero(reached)[0]) if reached.any() else None
    max_zero_gate=0.
    for i,w in enumerate(run['fields']['w']):
        a,b=run['edges'][:,:2].astype(int).T;outside=(w[a]+w[b])*.5<=1;outside&=~(seed[a]|seed[b]);max_zero_gate=max(max_zero_gate,float(run['fields']['d'][i,outside].max(initial=0)))
    return dict(settings=run['settings'],record=str(run['folder'].relative_to(ROOT)),nodes=len(xy),edges=len(run['edges']),occupied_area=float(h['body_area'][-1]),arena_area=float(run['mass'].sum()),body_components=count,largest_body_component_area=largest,target_first_contact_time=None if first is None else float(h['time'][first]),retained_length_D1=float(h['vein_length'][-1]),max_conductivity=float(run['fields']['d'][-1].max()),late_probe_calcium_range=[float(c.min()),float(c.max())],late_probe_flow_range=[float(q.min()),float(q.max())],late_calcium_period=None if len(peaks)<2 else float(np.median(np.diff(p['time'][late][peaks]))),max_vein_conductivity_outside_body_gate=max_zero_gate,max_fluid_residual=float(p['fluid_residual'].max()),max_energy_defect=float(p['energy_defect'].max()),source_fingerprint=run['engine']['source_fingerprint'])

def archive_case(name,run,output):
    target=output/'replay'/name;target.mkdir(parents=True,exist_ok=True)
    for file in ('nodes.csv','edges.csv','triangles.csv','scenario.json','raw/engine.json'):
        dest=target/file;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((run['folder']/file).read_bytes())
    for file in ('history.csv','probe.csv'):
        with (target/(file+'.gz')).open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as out:out.write((run['folder']/'raw'/file).read_bytes())
    indices=np.unique(np.linspace(0,len(run['history'])-1,9).round().astype(int));np.savez_compressed(target/'reference.npz',indices=indices,times=run['history']['time'][indices],**{key:np.asarray(field[indices]) for key,field in run['fields'].items()})
    sources=run['manifest']['software']['source_sha256']
    with (target/'source.tar.gz').open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as tar:
        for path in sorted(sources):
            data=(run['folder']/'source'/path).read_bytes();info=tarfile.TarInfo(path);info.size=len(data);info.mode=0o644;info.mtime=0;tar.addfile(info,io.BytesIO(data))
    (target/'reference-files.json').write_text(json.dumps({str(p.relative_to(target)):sha(p) for p in sorted(target.rglob('*')) if p.is_file() and p.name!='reference-files.json'},indent=2)+'\n')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--jobs',type=int,default=2);parser.add_argument('--cases',nargs='*');args=parser.parse_args()
    variants=dict(default={},source_front={'tau_front':20.},half_dt={'dt':.01},finer_mesh={'spacing':.4},no_feedback={'feedback':0.},printed_control={'hill':1})
    selected=args.cases or list(variants)
    if any(k not in variants for k in selected):parser.error('Unknown case')
    output=ROOT/'results/biology_validation';output.mkdir(parents=True,exist_ok=True);summaries={}
    existing=output/'validation.json'
    if existing.exists():summaries=json.loads(existing.read_text()).get('cases',{})
    def task(name):
        print('START',name,flush=True);r=run_biology(dict(DEFAULT_BIOLOGY,**variants[name]),progress=lambda v:print(name,round(v*100),flush=True) if round(v*100)%25==0 else None);return name,r
    with ThreadPoolExecutor(max_workers=max(1,min(2,args.jobs))) as pool:
        for future in as_completed([pool.submit(task,name) for name in selected]):
            name,run=future.result();summaries[name]=summarize(run);archive_case(name,run,output)
            existing.write_text(json.dumps(dict(scope='Exploratory numerical controls; not quantitative reproduction of Schenz et al. 2017 or biological validation.',cases=summaries),indent=2)+'\n');print('COMPLETE',name,json.dumps(summaries[name]),flush=True)
if __name__=='__main__':main()
