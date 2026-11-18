"""Reproducible inoculum/food experiments for the separate C++ particle model."""
from dataclasses import dataclass
from datetime import datetime, timezone
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import uuid

import numpy as np

try:
    from .spatial_data import ROOT, default_scene, validate_scene
except ImportError:
    from spatial_data import ROOT, default_scene, validate_scene

DEFAULT_GROWTH = dict(start_id='940GZZLUKSX', seed=42, steps=1600, frame_every=10,
                      width=480, seed_count=220, seed_radius=11., max_agents=14000,
                      division_interval=4, sensor_distance=9., sensor_angle=45., turn_angle=45.,
                      decay=.08, food_strength=8., food_range=30., river_aversion=0.)


def sha256_file(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def prepare_growth(scene, settings, model_version=2):
    if model_version not in (1,2):raise ValueError('Unsupported growth model version.')
    validate_scene(scene)
    if set(settings)!=set(DEFAULT_GROWTH):raise ValueError('Incomplete growth settings.')
    for key,low,high in [('seed',0,2**31-1),('steps',100,4000),('frame_every',1,100),('width',160,640),
                         ('seed_count',1,1000),('max_agents',500,30000),('division_interval',2,20)]:
        value=settings[key]
        if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:
            raise ValueError(f'{key} must be an integer in [{low}, {high}].')
    for key,low,high in [('seed_radius',2,30),('sensor_distance',1,30),('sensor_angle',1,90),
                         ('turn_angle',1,90),('decay',.01,.5),('food_strength',0,30),('food_range',1,100),('river_aversion',0,30)]:
        value=settings[key]
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError(f'Invalid growth parameter: {key}.')
    if settings['steps']%settings['frame_every'] or settings['steps']//settings['frame_every']>400:
        raise ValueError('Updates must divide exactly into at most 400 recorded intervals.')
    if settings['max_agents']<settings['seed_count']:raise ValueError('Initial population exceeds its limit.')
    foods=[copy.deepcopy(node) for node in scene['nodes'] if node['kind']=='station']
    if not 2<=len(foods)<=80:raise ValueError('Choose 2–80 station food sites.')
    starts=[node for node in foods if node['key']==settings['start_id']]
    if not starts:raise ValueError('The starting station must be one of the food sites.')
    xy=np.array([[node['x'],node['y']] for node in foods])
    x0,y0=xy.min(axis=0)-1.2;x1,y1=xy.max(axis=0)+1.2
    width=settings['width'];cell=(x1-x0)/width;height=math.ceil((y1-y0)/cell)
    if height<32 or height>600:raise ValueError('The selected arena has an unsupported aspect ratio.')
    y1=y0+height*cell
    extent=[float(x0),float(x1),float(y0),float(y1)]
    pixels=(xy-[x0,y0])/cell
    start=foods.index(starts[0]);sx,sy=pixels[start]
    xx=x0+(np.arange(width)+.5)*cell;yy=y0+(np.arange(height)+.5)*cell
    blocked=np.zeros((height,width),dtype=np.uint8)
    for left,bottom,right,top in scene['barriers']:
        blocked|=((xx[None,:]>=left)&(xx[None,:]<=right)&(yy[:,None]>=bottom)&(yy[:,None]<=top)).astype(np.uint8)
    if blocked[np.floor(pixels[:,1]).astype(int),np.floor(pixels[:,0]).astype(int)].any():
        raise ValueError('A food site is inside a restricted area.')
    river=np.zeros_like(blocked,dtype=np.float32)
    for way in scene['geography']['river']:
        projected=(np.array(way['xy_km'])-[x0,y0])/cell
        for a,b in zip(projected[:-1],projected[1:]):
            count=max(2,int(np.max(np.abs(b-a))*2)+1)
            points=np.linspace(a,b,count);ij=np.floor(points).astype(int)
            inside=(ij[:,0]>=0)&(ij[:,0]<width)&(ij[:,1]>=0)&(ij[:,1]<height)
            river[ij[inside,1],ij[inside,0]]=1
    # A local 3-cell-wide repellent band. It is not a measured river bank width.
    padded=np.pad(river,1)
    river=np.maximum.reduce([padded[dy:dy+height,dx:dx+width] for dy in range(3) for dx in range(3)])
    config={key:settings[key] for key in DEFAULT_GROWTH if key!='start_id'}
    config.update(height=height,initial_x=float(sx),initial_y=float(sy),schema_version=model_version)
    return foods,pixels,extent,blocked,river,config


@dataclass
class GrowthRun:
    scene:dict
    settings:dict
    foods:list
    extent:list
    trail:np.ndarray
    occupied:np.ndarray
    stats:np.ndarray
    contacts:np.ndarray
    folder:Path
    activity:np.ndarray
    model_version:int

    @property
    def steps(self):return self.stats[:,1].astype(int)


def load_growth_run(folder):
    folder=Path(folder);manifest=json.loads((folder/'scenario.json').read_text())
    models={'chemotactic_particles_with_growth_v1':1,'chemotactic_particles_with_growth_v2':2}
    if manifest.get('model') not in models:raise ValueError('Unsupported growth model.')
    model_version=models[manifest['model']]
    scene,settings=manifest['scene'],manifest['settings']
    foods,pixels,extent,blocked,river,config=prepare_growth(scene,settings,model_version)
    if manifest['config']!=config or not np.allclose(manifest['extent'],extent,rtol=0,atol=1e-12):
        raise ValueError('Recorded arena does not match scenario.')
    with (folder/'output/stats.csv').open() as stream:header=stream.readline().strip()
    if header!='frame,step,agents,food_reached,occupied_cells,trail_mass,births,deaths':raise ValueError('Invalid growth history header.')
    stats=np.loadtxt(folder/'output/stats.csv',skiprows=1,delimiter=',',ndmin=2)
    frames=settings['steps']//settings['frame_every']+1;height,width=blocked.shape
    if stats.shape!=(frames,8) or not np.isfinite(stats).all():raise ValueError('Incomplete or nonfinite growth history.')
    if not np.array_equal(stats[:,0],np.arange(frames)) or not np.array_equal(stats[:,1],np.arange(frames)*settings['frame_every']):
        raise ValueError('Incorrect growth frame ordering.')
    if not np.array_equal(stats[:,[0,1,2,3,4,6,7]],np.floor(stats[:,[0,1,2,3,4,6,7]])) or np.any(stats<0):
        raise ValueError('Invalid growth counters.')
    if (stats[0,2]!=settings['seed_count'] or np.any(stats[:,2]>settings['max_agents']) or
        np.any(stats[:,2]!=stats[:,4]) or np.any(stats[:,2]!=settings['seed_count']+stats[:,6]-stats[:,7]) or
        np.any(np.diff(stats[:,6:8],axis=0)<0)):
        raise ValueError('Particle population accounting is inconsistent.')
    for filename,itemsize in [('trail.f32',4),('occupied.u8',1)]:
        if (folder/'output'/filename).stat().st_size!=frames*height*width*itemsize:raise ValueError('Incomplete growth field file.')
    trail=np.memmap(folder/'output/trail.f32',mode='r',dtype='<f4',shape=(frames,height,width))
    occupied=np.memmap(folder/'output/occupied.u8',mode='r',dtype='u1',shape=trail.shape)
    for index in range(frames):
        field=trail[index];density=occupied[index]
        if not np.isfinite(field).all() or np.any(field<0) or np.any(density>1):raise ValueError('Nonfinite/negative trail or invalid occupancy.')
        if field[blocked.astype(bool)].any() or density[blocked.astype(bool)].any():raise ValueError('Growth enters a restricted cell.')
        if density.sum()!=stats[index,2] or not math.isclose(float(field.sum(dtype=np.float64)),stats[index,5],rel_tol=1e-7,abs_tol=1e-6):
            raise ValueError('Field data do not match recorded statistics.')
    contacts=np.loadtxt(folder/'output/food.csv',delimiter=',',skiprows=1,ndmin=2)
    if (contacts.shape!=(len(foods),2) or not np.isfinite(contacts).all() or not np.array_equal(contacts[:,0],np.arange(len(foods))) or
        np.any(contacts[:,1]!=np.floor(contacts[:,1])) or np.any(contacts[:,1]<-1) or np.any(contacts[:,1]>settings['steps'])):
        raise ValueError('Invalid food contact history.')
    contacts=contacts[:,1].astype(int)
    reached=(contacts[None,:]>=0)&(contacts[None,:]<=stats[:,1,None])
    if not np.array_equal(reached.sum(axis=1),stats[:,3]):raise ValueError('Food contacts do not match growth counts.')
    # Current local occupancy is separate from historical first contact and connectivity.
    activity=np.zeros((frames,len(foods)),dtype=int)
    for food,(x,y) in enumerate(pixels):
        xx,yy=np.meshgrid(np.arange(max(0,int(x)-5),min(width,int(x)+6)),np.arange(max(0,int(y)-5),min(height,int(y)+6)))
        inside=(xx+.5-x)**2+(yy+.5-y)**2<=16
        activity[:,food]=occupied[:,yy[inside],xx[inside]].sum(axis=1)
    activity_path=folder/'output/activity.csv'
    if model_version==2 or activity_path.exists():
        recorded=np.loadtxt(activity_path,skiprows=1,delimiter=',',ndmin=2)
        expected=np.column_stack((np.repeat(np.arange(frames),len(foods)),np.tile(np.arange(len(foods)),frames),activity.ravel()))
        if not np.array_equal(recorded,expected):raise ValueError('Current food occupancy does not match the saved field.')
    # Check that the initial colony really is local, not a revealed global mesh.
    yy,xx=np.nonzero(occupied[0]);distance=np.hypot(xx+.5-config['initial_x'],yy+.5-config['initial_y'])
    if np.any(distance>settings['seed_radius']+math.sqrt(2)):raise ValueError('Initial colony lies outside inoculum.')
    checks=json.loads((folder/'checksums.json').read_text())
    expected_paths={'inputs/input.cfg','inputs/food.csv','inputs/blocked.bin','inputs/river.bin','output/trail.f32','output/occupied.u8','output/stats.csv','output/food.csv','output/metadata.txt','scenario.json'}
    if model_version==2 or activity_path.exists():expected_paths.add('output/activity.csv')
    if set(checks)!=expected_paths:raise ValueError('Incomplete growth checksums.')
    for relative,digest in checks.items():
        if sha256_file(folder/relative)!=digest:raise ValueError('Growth record checksum mismatch: '+relative)
    if not np.array_equal(trail[0],occupied[0].astype(float)*5):raise ValueError('Initial trail does not match seeded particles.')
    for name,expected,dtype in [('blocked.bin',blocked,'u1'),('river.bin',river,'<f4')]:
        actual=np.fromfile(folder/'inputs'/name,dtype=dtype)
        if not np.array_equal(actual,expected.ravel()):raise ValueError('Recorded mask does not match the scenario.')
    food_input=np.loadtxt(folder/'inputs/food.csv',skiprows=1,delimiter=',',ndmin=2)
    if food_input.shape!=(len(foods),3) or not np.allclose(food_input,np.column_stack((np.arange(len(foods)),pixels)),rtol=0,atol=1e-10):
        raise ValueError('Recorded food coordinates do not match the scenario.')
    text=(folder/'inputs/input.cfg').read_text()
    if text!=''.join(f'{key}={value}\n' for key,value in config.items()):raise ValueError('Recorded config does not match the scenario.')
    return GrowthRun(scene,settings,foods,extent,trail,occupied,stats,contacts,folder,activity,model_version)


def run_growth_experiment(scene,settings,root=None,cancel=None,model_version=2):
    scene,settings=copy.deepcopy(scene),copy.deepcopy(settings)
    foods,pixels,extent,blocked,river,config=prepare_growth(scene,settings,model_version)
    root=Path(root or ROOT/'results/growth_runs')
    folder=root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]);inputs=folder/'inputs';inputs.mkdir(parents=True)
    manifest=dict(schema_version=1,model=f'chemotactic_particles_with_growth_v{model_version}',scene=scene,settings=settings,extent=extent,config=config,
        interpretation='Particle activity and recent trail; not conductivity, tube radius, pressure or calibrated biological growth.',
        sources=['https://doi.org/10.1126/science.1177894','https://doi.org/10.1162/artl.2010.16.2.16202','https://arxiv.org/abs/1212.0023'],
        assumptions=['London station food layout is an analogy to the Tokyo laboratory experiment, not its numerical replication.',
            'Food cues recover when uncovered; nearby-particle counts do not establish connectivity.' if model_version==2 else 'Legacy permanently weakened food cues after first contact.',
            'Equal food sites are not passenger demand; iteration is not a biological hour.',
            'Optional Thames aversion is a hypothetical repellent; elevation never changes growth.'])
    manifest['food_protocol']='coverage-dependent cue: 0.05 while occupied, 1.0 when uncovered; refreshed every 10 updates' if model_version==2 else 'legacy once-visited cue: permanently 0.05'
    executable=ROOT/'build/physarum_growth'
    manifest['software']=dict(numpy=np.__version__,executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
            for pattern in ('src/*Growth*','src/growth_main.cpp','include/physarum/Growth*','desktop/growth_*.py') for path in sorted(ROOT.glob(pattern))})
    (folder/'scenario.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    (inputs/'input.cfg').write_text(''.join(f'{key}={value}\n' for key,value in config.items()))
    with (inputs/'food.csv').open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(['food','x','y']);writer.writerows((i,*point) for i,point in enumerate(pixels))
    blocked.tofile(inputs/'blocked.bin');river.astype('<f4').tofile(inputs/'river.bin')
    command=[str(executable),str(inputs/'input.cfg'),str(inputs),str(folder/'output')]
    try:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        elapsed=0
        while True:
            try:stdout,stderr=process.communicate(timeout=.2);break
            except subprocess.TimeoutExpired:
                elapsed+=.2
                if (cancel is not None and cancel.is_set()) or elapsed>180:
                    process.terminate()
                    try:process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:process.kill();process.communicate()
                    raise ValueError('Growth run cancelled or timed out.')
        (folder/'engine.log').write_text(stdout+stderr)
        if process.returncode:raise ValueError(stderr.strip())
        checks={str(path.relative_to(folder)):sha256_file(path)
                for directory in (inputs,folder/'output') for path in directory.iterdir() if path.is_file()}
        checks['scenario.json']=hashlib.sha256((folder/'scenario.json').read_bytes()).hexdigest()
        (folder/'checksums.json').write_text(json.dumps(checks,indent=2)+'\n')
        return load_growth_run(folder)
    except Exception as error:
        (folder/'failure.txt').write_text(str(error))
        raise ValueError(f'{error}\nRecorded inputs retained at {folder}') from error
