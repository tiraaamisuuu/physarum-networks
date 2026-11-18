#!/usr/bin/env python3
"""Paired legacy/recovering-cue runs: local occupancy, not network connectivity."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop.growth_data import DEFAULT_GROWTH,default_scene,run_growth_experiment,sha256_file


def execute(job):
    seed,version=job
    run=run_growth_experiment(default_scene(),{**DEFAULT_GROWTH,'seed':seed},model_version=version)
    late=run.steps>=run.settings['steps']-200
    return dict(seed=seed,version=version,folder=str(run.folder.relative_to(ROOT)),ever_visited=int(run.stats[-1,3]),
        nearby_final=int((run.activity[-1]>0).sum()),nearby_last_200_mean=float((run.activity[late]>0).sum(axis=1).mean()),
        scenario_sha256=sha256_file(run.folder/'scenario.json'),
        output_sha256={name:sha256_file(run.folder/'output'/name) for name in ['trail.f32','occupied.u8','stats.csv','food.csv']})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/verification/food-recovery.json')
    args=parser.parse_args()
    jobs=[(seed,version) for seed in (42,43,47) for version in (1,2)]
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(execute,jobs))
    report=dict(protocol='Three paired seeds; all other default settings unchanged. Current nearby occupied-cell count within radius 4; final and 1400–1600 inclusive window.',
        settings=DEFAULT_GROWTH,rows=rows,interpretation='Local activity, not connectivity, optimality, railway feasibility or biological validation.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    for row in rows:print(f'Seed {row["seed"]}, v{row["version"]}: {row["ever_visited"]} visited; {row["nearby_final"]} active nearby at end')


if __name__=='__main__':main()
