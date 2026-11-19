#!/usr/bin/env python3
"""Replay frozen biological inputs; compare sampled fields and full-rate probes."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
import gzip
import json
import subprocess
import tarfile
import tempfile
import uuid
import numpy as np
from desktop.biology_data import ROOT,sha

def main():
    parser=argparse.ArgumentParser();parser.add_argument('case',type=Path);parser.add_argument('--build-source',action='store_true',help='Build preserved source in a temporary directory.');args=parser.parse_args();case=args.case.resolve()
    references=json.loads((case/'reference-files.json').read_text())
    for name,digest in references.items():
        if Path(name).is_absolute() or '..' in Path(name).parts or sha(case/name)!=digest:raise ValueError('Invalid archived file: '+name)
    manifest=json.loads((case/'scenario.json').read_text());settings=manifest['settings'];engine=json.loads((case/'raw/engine.json').read_text());executable=ROOT/'build/physarum_biology'
    with tempfile.TemporaryDirectory(prefix='physarum-biology-source-') as temp:
        if args.build_source:
            source=Path(temp)/'source';source.mkdir()
            with tarfile.open(case/'source.tar.gz') as archive:archive.extractall(source,filter='data')
            for name,digest in manifest['software']['source_sha256'].items():
                if Path(name).is_absolute() or '..' in Path(name).parts or sha(source/name)!=digest:raise ValueError('Source snapshot checksum mismatch.')
            subprocess.run(['cmake','-S',str(source),'-B',str(source/'build'),'-DCMAKE_BUILD_TYPE=Release','-DBUILD_TESTING=OFF'],check=True,stdout=subprocess.DEVNULL)
            subprocess.run(['cmake','--build',str(source/'build'),'--target','physarum_biology','--parallel','2'],check=True,stdout=subprocess.DEVNULL);executable=source/'build/physarum_biology'
        output=ROOT/'results/biology_runs'/('replay-'+case.name+'-'+uuid.uuid4().hex[:8]);output.parent.mkdir(parents=True,exist_ok=True)
        cmd=[str(executable),str(case/'nodes.csv'),str(case/'edges.csv')]+[str(settings[k]) for k in ('duration','dt','hill','feedback','tau_front','save_interval')]+[str(engine['probe']),str(output)]
        if 'integrator' in settings:cmd.append(settings['integrator'])
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL);actual=json.loads((output/'engine.json').read_text())
        if actual['source_fingerprint']!=engine['source_fingerprint']:raise ValueError('Replayed engine source differs; use --build-source.')
        reference=np.load(case/'reference.npz');differences={}
        for key in ('c','phi','u','v','w','p','q','d'):
            count=engine['edges'] if key in ('q','d') else engine['nodes'];field=np.memmap(output/(key+'.f64'),dtype='<f8',mode='r',shape=(engine['frames'],count));differences[key]=float(np.abs(field[reference['indices']]-reference[key]).max())
        byte_equal={name:(output/name).read_bytes()==gzip.decompress((case/(name+'.gz')).read_bytes()) for name in ('history.csv','probe.csv')+(('global.csv',) if (case/'global.csv.gz').exists() else ())}
        report=dict(case=case.name,output=str(output),source_fingerprint=actual['source_fingerprint'],maximum_snapshot_absolute_differences=differences,full_history_and_probe_byte_equal=byte_equal)
        (output/'replay-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
