"""Documented spatial graph preparation and recorded-demand C++ experiments."""
from dataclasses import dataclass
from datetime import datetime,timezone
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import subprocess
import uuid

import numpy as np

try:
    from .run_data import ROOT
except ImportError:
    from run_data import ROOT

GEOGRAPHY = ROOT/'data/london/geography.json'
DEFAULT_SETTINGS={'current':2.,'gamma':1.8,'dt':.05,'duration':20.,'initial_conductivity':.5,
                  'neighbours':6,'river_penalty':2.,'seed':42,'demand_mode':'uniform_pairs',
                  'source_id':'940GZZLUPAC','sink_id':'940GZZLUSTD'}


def default_scene():
    geography=json.loads(GEOGRAPHY.read_text())
    lookup={node['tfl_id']:node for node in geography['station_catalog']}
    nodes=[]
    for key in geography['default_station_ids']:
        node=copy.deepcopy(lookup[key]);node['key']=key;nodes.append(node)
    return {'schema_version':1,'name':'Central London exploratory network','geography':geography,
            'nodes':nodes,'barriers':[]}


def intersects(a,b,c,d):
    """Closed line-segment intersection, including collinear contacts."""
    def cross(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    def between(p,q,r):return (min(p[0],r[0])-1e-10<=q[0]<=max(p[0],r[0])+1e-10 and
                              min(p[1],r[1])-1e-10<=q[1]<=max(p[1],r[1])+1e-10)
    x,y,z,w=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    if x*y<0 and z*w<0:return True
    return any(abs(value)<1e-10 and between(p,q,r) for value,p,q,r in
               [(x,a,c,b),(y,a,d,b),(z,c,a,d),(w,c,b,d)])


def hits_rectangle(a,b,rect):
    x0,y0,x1,y1=rect
    if x0<=a[0]<=x1 and y0<=a[1]<=y1 or x0<=b[0]<=x1 and y0<=b[1]<=y1:return True
    corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    return any(intersects(a,b,corners[i],corners[(i+1)%4]) for i in range(4))


def within_coverage(node,geography):
    bounds=geography.get('coverage_bounds_lat_lon')
    if bounds is None:return True  # Synthetic mathematical fixtures need no geographic bounds.
    south,west,north,east=bounds
    return south<=node['lat']<=north and west<=node['lon']<=east


def validate_scene(scene):
    if scene.get('schema_version')!=1:raise ValueError('Unsupported scenario version.')
    geography=scene['geography'];nodes=scene['nodes']
    if not isinstance(scene['name'],str) or not isinstance(geography['station_catalog'],list):
        raise ValueError('Invalid scenario labels or station catalogue.')
    for node in nodes:
        if node['kind'] not in ('station','junction') or not isinstance(node['name'],str):
            raise ValueError('Each node needs a station/junction role and a name.')
        if not all(math.isfinite(node[key]) for key in ('x','y','lat','lon')):
            raise ValueError('Node coordinates must be finite.')
        if not within_coverage(node,geography):
            raise ValueError(f'{node["name"]} is outside the cached Thames coverage. Use stations/junctions inside the central London study area; extend the geographic dataset before studying outer London.')
    for rect in scene['barriers']:
        if len(rect)!=4 or not all(math.isfinite(v) for v in rect) or rect[0]>=rect[2] or rect[1]>=rect[3]:
            raise ValueError('Restricted rectangles must have finite ordered bounds.')
    elevation=geography['elevation']
    heights=np.asarray(elevation['metres'],dtype=float)
    if (len(elevation['x'])<2 or len(elevation['y'])<2 or heights.shape!=(len(elevation['y']),len(elevation['x'])) or
        not np.isfinite(heights).all() or not np.all(np.diff(elevation['x'])>0) or not np.all(np.diff(elevation['y'])>0)):
        raise ValueError('Invalid elevation context grid.')
    for way in geography['river']:
        xy=np.asarray(way['xy_km'],dtype=float)
        if xy.ndim!=2 or xy.shape[1]!=2 or len(xy)<2 or not np.isfinite(xy).all():
            raise ValueError('Invalid river geometry.')


def validate_settings(settings):
    if set(settings)!=set(DEFAULT_SETTINGS):raise ValueError('Incomplete spatial experiment settings.')
    for key,low,high in [('current',.1,5),('gamma',.5,3),('dt',.01,.25),('duration',1,40),
                         ('initial_conductivity',.01,1),('river_penalty',0,10)]:
        v=settings[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError(f'{key} must be between {low:g} and {high:g}.')
    for key,low,high in [('neighbours',2,12),('seed',0,2**31-1)]:
        if isinstance(settings[key],bool) or int(settings[key])!=settings[key] or not low<=settings[key]<=high:
            raise ValueError(f'Invalid {key}.')
    if settings['demand_mode'] not in ('uniform_pairs','fixed_pair'):raise ValueError('Unknown demand mode.')
    steps=round(settings['duration']/settings['dt'])
    if steps>2000 or not math.isclose(steps*settings['dt'],settings['duration'],abs_tol=1e-9):
        raise ValueError('Duration must be a whole multiple of dt, with at most 2,000 updates.')
    return steps


def build_graph(scene,settings):
    validate_settings(settings)
    validate_scene(scene)
    nodes=scene['nodes']
    if not 3<=len(nodes)<=100:raise ValueError('Select 3–100 nodes for this dense-solver experiment.')
    if len({node['key'] for node in nodes})!=len(nodes):raise ValueError('Node keys must be unique.')
    xy=np.array([[node['x'],node['y']] for node in nodes],dtype=float)
    if not np.isfinite(xy).all():raise ValueError('Node coordinates must be finite.')
    distances=np.linalg.norm(xy[:,None,:]-xy[None,:,:],axis=2)
    if np.any((distances+np.eye(len(nodes)))<1e-6):raise ValueError('Two nodes occupy the same position.')
    demand_nodes=[i for i,node in enumerate(nodes) if node['kind']=='station']
    if len(demand_nodes)<2:raise ValueError('At least two demand stations are required.')
    river_segments=[]
    for way in scene['geography']['river']:
        points=way['xy_km'];river_segments.extend(zip(points[:-1],points[1:]))
    pairs=set()
    for i in range(len(nodes)):
        order=sorted((j for j in range(len(nodes)) if i!=j),key=lambda j:(distances[i,j],j))
        for j in order[:int(settings['neighbours'])]:pairs.add(tuple(sorted((i,j))))
    edges=[]
    adjacency=[[] for _ in nodes]
    for i,j in sorted(pairs):
        if any(hits_rectangle(xy[i],xy[j],rect) for rect in scene['barriers']):continue
        crosses=any(intersects(xy[i],xy[j],a,b) for a,b in river_segments)
        distance=float(distances[i,j])
        cost=distance+(settings['river_penalty'] if crosses else 0)
        edges.append({'id':len(edges),'from':i,'to':j,'distance_km':distance,'river_crossing':crosses,'length':cost})
        adjacency[i].append(j);adjacency[j].append(i)
    reached={demand_nodes[0]};stack=list(reached)
    while stack:
        for node in adjacency[stack.pop()]:
            if node not in reached:reached.add(node);stack.append(node)
    if any(node not in reached for node in demand_nodes):
        raise ValueError('The candidate graph separates demand stations. Increase neighbours or remove a restricted area. No connections have been invented to repair it.')
    if not edges or len(edges)>900:raise ValueError('Candidate graph must contain 1–900 edges.')
    return edges,demand_nodes


def demand_schedule(scene,settings,steps):
    demand=[i for i,node in enumerate(scene['nodes']) if node['kind']=='station']
    if settings['demand_mode']=='fixed_pair':
        keys={node['key']:i for i,node in enumerate(scene['nodes']) if node['kind']=='station'}
        if settings['source_id'] not in keys or settings['sink_id'] not in keys:
            raise ValueError('Choose source and sink from the selected stations.')
        source,sink=keys[settings['source_id']],keys[settings['sink_id']]
        if source==sink:raise ValueError('Source and sink must differ.')
        return [(source,sink)]*(steps+1)
    if len(demand)<2:raise ValueError('At least two demand stations are required.')
    rng=random.Random(int(settings['seed']))
    return [tuple(rng.sample(demand,2)) for _ in range(steps+1)]


@dataclass
class SpatialRun:
    scene:dict
    settings:dict
    edges:list
    times:np.ndarray
    d:np.ndarray
    q:np.ndarray
    p:np.ndarray
    sources:np.ndarray
    sinks:np.ndarray
    diagnostics:np.ndarray
    folder:Path


def load_spatial_run(folder):
    folder=Path(folder)
    manifest=json.loads((folder/'scenario.json').read_text())
    scene,settings,edges=manifest['scene'],manifest['settings'],manifest['edges']
    validate_scene(scene)
    steps=validate_settings(settings);n=len(scene['nodes']);m=len(edges)
    if n<3 or n>100 or m<1 or m>900:raise ValueError('Recorded graph is outside the supported size.')
    path=folder/'output/history.csv'
    expected='step,time,edge,conductivity,flow,pressure_from,pressure_to,conservation_inf,backward_error,scaled_rcond,source,sink'
    with path.open() as stream:header=stream.readline().strip()
    if header!=expected:raise ValueError('Unsupported spatial history columns.')
    raw=np.loadtxt(path,delimiter=',',skiprows=1,ndmin=2)
    if raw.shape!=((steps+1)*m,12) or not np.isfinite(raw).all():raise ValueError('Incomplete or nonfinite history.')
    raw=raw.reshape(steps+1,m,12)
    times=np.arange(steps+1)*settings['dt']
    if (not np.array_equal(raw[:,:,0],np.broadcast_to(np.arange(steps+1)[:,None],(steps+1,m))) or
        not np.array_equal(raw[:,:,2],np.broadcast_to(np.arange(m),(steps+1,m))) or
        not np.allclose(raw[:,:,1],times[:,None],atol=1e-10,rtol=0)):
        raise ValueError('State ordering or times do not match the experiment.')
    sources=raw[:,0,10].astype(int);sinks=raw[:,0,11].astype(int)
    if (not np.all(raw[:,:,10]==sources[:,None]) or not np.all(raw[:,:,11]==sinks[:,None]) or
        np.any(sources<0) or np.any(sources>=n) or np.any(sinks<0) or np.any(sinks>=n) or np.any(sources==sinks)):
        raise ValueError('Invalid per-state terminal pair.')
    recorded=np.loadtxt(folder/'output/demands.csv',delimiter=',',skiprows=1,ndmin=2)
    input_demands=np.loadtxt(folder/'inputs/demands.csv',delimiter=',',skiprows=1,ndmin=2)
    if (recorded.shape!=(steps+1,3) or not np.array_equal(recorded[:,0],np.arange(steps+1)) or
        not np.array_equal(recorded,input_demands) or not np.array_equal(recorded[:,1:],np.column_stack((sources,sinks)))):
        raise ValueError('Recorded demand schedule does not match the simulation.')
    expected_edges,_=build_graph(scene,settings)
    if len(expected_edges)!=m:raise ValueError('Recorded candidate graph does not match the scenario.')
    for actual,expected_edge in zip(edges,expected_edges):
        for key in ('id','from','to','river_crossing'):
            if actual[key]!=expected_edge[key]:raise ValueError('Recorded candidate graph does not match the scenario.')
        for key in ('length','distance_km'):
            if not math.isclose(actual[key],expected_edge[key],rel_tol=1e-12,abs_tol=1e-12):
                raise ValueError('Recorded costs do not match the scenario.')
    expected_csv=np.array([[e['id'],e['from'],e['to'],e['length']] for e in edges])
    for file in ('inputs/edges.csv','output/edges.csv'):
        values=np.loadtxt(folder/file,delimiter=',',skiprows=1,ndmin=2)
        if values.shape!=expected_csv.shape or not np.allclose(values,expected_csv,rtol=1e-12,atol=1e-12):
            raise ValueError('Graph CSV does not match the recorded candidate costs.')
    d,q=raw[:,:,3].copy(),raw[:,:,4].copy()
    if np.any(d<0):raise ValueError('Negative conductivity in history.')
    if not np.allclose(d[0],settings['initial_conductivity'],rtol=0,atol=1e-12):raise ValueError('Initial D mismatch.')
    p=np.full((steps+1,n),np.nan);balance=np.zeros_like(p)
    for edge in edges:
        i,u,v=edge['id'],edge['from'],edge['to']
        if not 0<=i<m or not 0<=u<n or not 0<=v<n or not math.isfinite(edge['length']) or edge['length']<=0:
            raise ValueError('Invalid recorded edge.')
        for node,column in ((u,5),(v,6)):
            already=np.isfinite(p[:,node])
            if not np.allclose(p[already,node],raw[already,i,column],rtol=1e-10,atol=1e-12):raise ValueError('Conflicting pressures.')
            p[:,node]=raw[:,i,column]
        expected_q=d[:,i]/edge['length']*(raw[:,i,5]-raw[:,i,6])
        if not np.allclose(expected_q,q[:,i],rtol=1e-10,atol=1e-12):raise ValueError('Pressure-flow equation mismatch.')
        balance[:,u]+=q[:,i];balance[:,v]-=q[:,i]
    p=np.nan_to_num(p,nan=0.)
    indices=np.arange(steps+1)
    balance[indices,sources]-=settings['current'];balance[indices,sinks]+=settings['current']
    if np.max(np.abs(balance))>1e-12+1e-10*settings['current']:raise ValueError('Demand is not conserved.')
    power=np.abs(q[:-1])**settings['gamma']
    predicted=(1-settings['dt'])*d[:-1]+settings['dt']*power/(1+power)
    if not np.allclose(predicted,d[1:],rtol=1e-10,atol=1e-12):raise ValueError('Conductivity history violates the Euler update.')
    diagnostics=raw[:,0,7:10].copy()
    if not np.all(raw[:,:,7:10]==diagnostics[:,None,:]):raise ValueError('Inconsistent diagnostics.')
    if (np.any(diagnostics[:,:2]<0) or np.any(diagnostics[:,0]>1e-12+1e-10*settings['current']) or
        np.any(diagnostics[:,1]>1e-12) or np.any(diagnostics[:,2]<1e-14)):
        raise ValueError('Recorded solver diagnostics exceed acceptance limits.')
    return SpatialRun(scene,settings,edges,times,d,q,p,sources,sinks,diagnostics,folder)


def run_spatial_experiment(executable,scene,settings,root=None):
    steps=validate_settings(settings)
    scene=copy.deepcopy(scene);settings=copy.deepcopy(settings)
    edges,_=build_graph(scene,settings)
    schedule=demand_schedule(scene,settings,steps)
    root=Path(root or ROOT/'results/spatial_runs')
    folder=root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    inputs=folder/'inputs';inputs.mkdir(parents=True)
    manifest={'schema_version':1,'scene':scene,'settings':settings,'edges':edges,
              'demand_protocol':'fixed pair' if settings['demand_mode']=='fixed_pair' else 'uniform distinct station pair at each Euler step',
              'python':platform.python_version(),'elevation_role':'visual context only',
              'cost_rule':'effective_length_km = straight_line_distance_km + river_penalty_km * any_Thames_centreline_crossing',
              'river_penalty_status':'user assumption, not a calibrated engineering cost'}
    manifest['software']={'numpy':np.__version__,
        'executable_sha256':hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
        'source_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                         for pattern in ('src/*.cpp','include/physarum/*.hpp','desktop/spatial_*.py')
                         for path in sorted(ROOT.glob(pattern))}}
    (folder/'scenario.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    with (inputs/'edges.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['edge','from','to','length'])
        writer.writerows((e['id'],e['from'],e['to'],e['length']) for e in edges)
    with (inputs/'demands.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['step','source','sink'])
        writer.writerows((i,*pair) for i,pair in enumerate(schedule))
    config={key:settings[key] for key in ('dt','gamma','current','initial_conductivity')}
    config.update(steps=steps,source=schedule[0][0],sink=schedule[0][1])
    (inputs/'input.cfg').write_text(''.join(f'{key}={value}\n' for key,value in config.items()))
    command=[str(executable),str(inputs/'input.cfg'),str(folder/'output'),str(inputs/'edges.csv'),str(len(scene['nodes'])),str(inputs/'demands.csv')]
    try:
        result=subprocess.run(command,capture_output=True,text=True,timeout=90)
        (folder/'engine.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise ValueError(result.stderr.strip().removeprefix('Error: '))
        return load_spatial_run(folder)
    except Exception as error:
        (folder/'failure.txt').write_text(str(error))
        raise ValueError(f'{error}\nInputs and any partial output retained in {folder}') from error
