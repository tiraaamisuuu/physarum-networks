#!/usr/bin/env python3
"""Matched-input integration study. Earlier biology_validation is preserved."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import gzip
import json
import numpy as np
from desktop.biology_data import ROOT,DEFAULT_BIOLOGY,run_biology,sha
from analysis.validate_biology import summarize,archive_case

BASELINE=dict(arena='snake',spacing=.5,seed=42,duration=1280.,dt=.02,hill=4,feedback=.01,tau_front=2.,save_interval=8.,integrator='legacy')
VARIANTS={'legacy':('legacy',.02),'midpoint_coarse':('midpoint',.04),'midpoint':('midpoint',.02),'midpoint_half':('midpoint',.01),'midpoint_fine':('midpoint',.005)}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cases',nargs='*',choices=VARIANTS);args=parser.parse_args();output=ROOT/'results/biology_integration';output.mkdir(parents=True,exist_ok=True);path=output/'validation.json'
    report=json.loads(path.read_text()) if path.exists() else dict(scope='Matched integration study of an uncalibrated cooperative growth variant; no biological validation implied.',cases={})
    runs={}
    def task(name):
        method,dt=VARIANTS[name];print('START',name,flush=True)
        r=run_biology(dict(BASELINE,integrator=method,dt=dt),progress=lambda v:print(name,round(v*100),flush=True) if round(v*100)%25==0 else None)
        frozen=ROOT/'results/biology_validation/replay/default'
        for f in ('nodes.csv','edges.csv','triangles.csv'):
            if sha(r['folder']/f)!=sha(frozen/f):raise ValueError('Study did not preserve the frozen spatial inputs.')
        return name,r
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(task,name) for name in (args.cases or list(VARIANTS))]):
            name,r=future.result();runs[name]=r;item=summarize(r);g=r['global_history'];use=g['time']>=1200;t=g['time'][use]
            item['last_80_time_mean_volume']=float(np.trapezoid(g['vein_volume'][use],t)/(t[-1]-t[0]));item['last_80_time_mean_retained_length_D1']=float(np.trapezoid(g['retained_length_D1'][use],t)/(t[-1]-t[0]));item['global_sample_interval']=r['settings']['dt'];item['integrator']=r['settings']['integrator']
            if name=='legacy':
                ref=np.load(ROOT/'results/biology_validation/replay/default/reference.npz');item['legacy_reference_snapshot_max_difference']={k:float(np.abs(r['fields'][k][ref['indices']]-ref[k]).max()) for k in r['fields']};item['legacy_reference_probe_history_byte_equal']={f:(r['folder']/'raw'/f).read_bytes()==gzip.decompress((ROOT/'results/biology_validation/replay/default'/(f+'.gz')).read_bytes()) for f in ('history.csv','probe.csv')}
            report['cases'][name]=item;archive_case(name,r,output);path.write_text(json.dumps(report,indent=2)+'\n');print('COMPLETE',name,json.dumps(item),flush=True)
    # Archive comparisons at the same nine stored times; rerunning a subset still works.
    if (output/'replay/midpoint_fine/reference.npz').exists():
        ref=np.load(output/'replay/midpoint_fine/reference.npz');comparisons={}
        for name in VARIANTS:
            sample=output/'replay'/name/'reference.npz'
            if not sample.exists():continue
            a=np.load(sample)
            if not np.array_equal(a['times'],ref['times']):raise ValueError('Incommensurate reference times.')
            comparisons[name]={k:float(np.abs(a[k]-ref[k]).max()) for k in ('c','phi','u','v','w','p','q','d')}
        report['maximum_nine_snapshot_difference_to_midpoint_dt_0005']=comparisons
        path.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
