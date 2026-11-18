#!/usr/bin/env python3
"""Replay a frozen validation mesh/forcing and compare archived numerical snapshots."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop.mesh_data import ROOT,load_mesh_run,mesh_metrics,capture_source_snapshot
from desktop.growth_data import sha256_file


def replay_case(case,output=None,verbose=True):
    case=Path(case);folder=Path(output) if output else Path(tempfile.mkdtemp(prefix='physarum-replay-'))
    if folder.exists() and any(folder.iterdir()):raise ValueError('Choose a new or empty output directory; existing records are never overwritten.')
    folder.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(gzip.decompress((case/'scenario.json.gz').read_bytes()))
    manifest['replay_reference_software']=manifest['software'];manifest['software']=capture_source_snapshot(folder);manifest['software']['replay_script_sha256']=sha256_file(Path(__file__))
    (folder/'scenario.json').write_text(json.dumps(manifest,indent=2)+'\n');shutil.copytree(case/'inputs',folder/'inputs')
    ip=folder/'inputs'
    subprocess.run([str(ROOT/'build/physarum_mesh'),str(ip/'input.cfg'),str(ip/'edges.csv'),str(len(manifest['mesh']['nodes'])),str(ip/'initial.csv'),str(ip/'demands.csv'),str(folder/'output')],check=True,timeout=240,capture_output=not verbose)
    checks={str(p.relative_to(folder)):sha256_file(p) for directory in (ip,folder/'output') for p in directory.iterdir()};checks['scenario.json']=sha256_file(folder/'scenario.json');(folder/'checksums.json').write_text(json.dumps(checks,indent=2)+'\n')
    r=load_mesh_run(folder);reference=np.load(case/'reference.npz');states=reference['states']
    for key in ('d','q','p'):
        values=getattr(r,key)[states];np.testing.assert_allclose(values,reference[key],rtol=2e-7,atol=2e-8)
        if verbose:print(key,'max absolute snapshot difference',float(np.max(np.abs(values-reference[key]))))
    original=json.loads((case/'original-checksums.json').read_text())
    if verbose:print('Byte-identical numeric output:',all(checks[k]==original[k] for k in checks if k.startswith('output/') and not k.endswith('metadata.txt')))
    return r


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('case',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    r=replay_case(args.case,args.output);print(mesh_metrics(r,len(r.times)-1,routes=True));print('Replayed run:',r.folder)

if __name__=='__main__':main()
