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
from desktop.mesh_data import ROOT,load_mesh_run,mesh_metrics
from desktop.growth_data import sha256_file


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('case',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    folder=args.output or Path(tempfile.mkdtemp(prefix='physarum-replay-'));folder.mkdir(parents=True,exist_ok=True)
    if (folder/'scenario.json').exists():raise ValueError('Choose a new output directory; existing runs are never overwritten.')
    manifest=json.loads(gzip.decompress((args.case/'scenario.json.gz').read_bytes()))
    manifest['replay_reference_software']=manifest['software'];manifest['software']={'executable_sha256':sha256_file(ROOT/'build/physarum_mesh'),'replay_script_sha256':sha256_file(Path(__file__))}
    (folder/'scenario.json').write_text(json.dumps(manifest,indent=2)+'\n');shutil.copytree(args.case/'inputs',folder/'inputs')
    ip=folder/'inputs'
    subprocess.run([str(ROOT/'build/physarum_mesh'),str(ip/'input.cfg'),str(ip/'edges.csv'),str(len(manifest['mesh']['nodes'])),str(ip/'initial.csv'),str(ip/'demands.csv'),str(folder/'output')],check=True,timeout=240)
    checks={str(p.relative_to(folder)):sha256_file(p) for directory in (ip,folder/'output') for p in directory.iterdir()};checks['scenario.json']=sha256_file(folder/'scenario.json');(folder/'checksums.json').write_text(json.dumps(checks,indent=2)+'\n')
    r=load_mesh_run(folder);reference=np.load(args.case/'reference.npz');states=reference['states']
    for key in ('d','q','p'):
        values=getattr(r,key)[states];np.testing.assert_allclose(values,reference[key],rtol=2e-7,atol=2e-8);print(key,'max absolute snapshot difference',float(np.max(np.abs(values-reference[key]))))
    original=json.loads((args.case/'original-checksums.json').read_text());print('Byte-identical numeric output:',all(checks[k]==original[k] for k in checks if k.startswith('output/') and not k.endswith('metadata.txt')))
    print(mesh_metrics(r,len(r.times)-1,routes=True));print('Replayed run:',folder)

if __name__=='__main__':main()
