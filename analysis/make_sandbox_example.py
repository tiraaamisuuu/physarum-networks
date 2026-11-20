#!/usr/bin/env python3
"""Compute a supplied sandbox design and export its actual retained route."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop.mesh_data import run_mesh_experiment,load_mesh_run
from desktop.mesh_routes import retained_route
from desktop.mesh_plot import export_snapshot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--example',choices=['obstacle','corridors','network'],default='obstacle')
    parser.add_argument('--run',type=Path,help='Render an existing complete record matching the selected example.')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--figure',type=Path)
    args=parser.parse_args()
    filename={'obstacle':'obstacle-sandbox','corridors':'unequal-corridors','network':'eight-food-network'}[args.example]
    output=args.output or ROOT/'tmp'/('sandbox-public-example' if args.example=='obstacle' else filename+'-export')
    figure=args.figure or ROOT/'docs/assets'/('sandbox-pathfinding.png' if args.example=='obstacle' else filename+'.png')
    design=json.loads((ROOT/'experiments/designs'/f'{filename}.json').read_text())
    run=load_mesh_run(args.run) if args.run else run_mesh_experiment(design['scene'],design['settings'])
    if run.scene!=design['scene'] or run.settings!=design['settings']:raise ValueError('Record does not match the selected example design.')
    frame=len(run.times)-1;route=retained_route(run,frame,0,run.food_count-1,1e-4)
    if route is None:raise ValueError('No retained route in this example; inspect the complete run.')
    export_snapshot(run,frame,output,names=True,route=route)
    figure.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(output/'network.png',figure)
    print(f'Complete record: {run.folder}\nRoute: {route["length_km"]:.6f} km; direct {route["direct_km"]:.6f} km\nFigure and numeric exports: {output}')


if __name__=='__main__':main()
