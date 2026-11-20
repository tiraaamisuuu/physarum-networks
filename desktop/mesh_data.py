"""Fine spatial mesh experiments using the Tero pressure-flow/sigmoid equations."""
from dataclasses import dataclass
from datetime import datetime,timezone
import copy
import csv
import heapq
import hashlib
import json
import math
from pathlib import Path
from pathlib import PurePosixPath
import random
import platform
import subprocess
import uuid
import gzip
import io
import tarfile

import numpy as np
from matplotlib.tri import Triangulation
from pyproj import Transformer
try:
    from .spatial_data import ROOT,default_scene,validate_scene,hits_rectangle,intersects,is_food
    from .growth_data import sha256_file
except ImportError:
    from spatial_data import ROOT,default_scene,validate_scene,hits_rectangle,intersects,is_food
    from growth_data import sha256_file

DEFAULT_MESH=dict(seed=42,spacing=.45,current=2.,gamma=1.8,dt=.0125,duration=30.,switch_interval=.05,
    initial_conductivity=.5,initial_noise=.1,river_penalty=0.,demand_mode='random_pairs',
    source_id='940GZZLUKSX',sink_id='940GZZLUSTD',integrator='heun')
DEFAULT_CUTOFF=1e-4


def validate_mesh_settings(settings):
    if set(settings) not in (set(DEFAULT_MESH),set(DEFAULT_MESH)-{'integrator'}):raise ValueError('Incomplete tube-model settings.')
    if settings.get('integrator','euler') not in ('euler','heun'):raise ValueError('Integrator must be euler or heun.')
    if isinstance(settings['seed'],bool) or not isinstance(settings['seed'],int) or not 0<=settings['seed']<2**31:raise ValueError('Seed must be an integer from 0 to 2³¹−1.')
    for key,low,high in [('spacing',.25,1.5),('current',.1,5),('gamma',.5,3),('dt',.005,.25),('duration',1,40),
                         ('switch_interval',.01,2),('initial_conductivity',.01,1),('initial_noise',0,.5),('river_penalty',0,10)]:
        v=settings[key]
        if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not low<=v<=high:raise ValueError(f'{key} must be in [{low}, {high}].')
    steps=round(settings['duration']/settings['dt']);hold=round(settings['switch_interval']/settings['dt'])
    if steps<1 or steps>6000 or not math.isclose(steps*settings['dt'],settings['duration'],abs_tol=1e-10):raise ValueError('Duration must be an integer multiple of dt, at most 6,000 updates.')
    if hold<1 or not math.isclose(hold*settings['dt'],settings['switch_interval'],abs_tol=1e-10):raise ValueError('Demand switching interval must be an integer multiple of dt. Keep it fixed when refining dt.')
    if settings['demand_mode'] not in ('random_pairs','fixed_pair','weighted_pairs'):raise ValueError('Unknown tube demand protocol.')
    return steps,hold


def effective_mesh_settings(settings):
    return {**settings,'integrator':settings.get('integrator','euler')}


def mesh_config(settings):
    steps,_=validate_mesh_settings(settings);cfg={key:settings[key] for key in ('dt','gamma','current')};cfg['steps']=steps
    if 'integrator' in settings:cfg['integrator']=settings['integrator']
    return ''.join(f'{key}={value}\n' for key,value in cfg.items())


def mesh_raw_bytes(mesh,settings):
    steps,_=validate_mesh_settings(settings);m,n=len(mesh['edges']),len(mesh['nodes'])
    return 8*((steps+1)*(2*m+n)+(steps*(m+n) if settings.get('integrator','euler')=='heun' else 0))


def capture_source_snapshot(folder):
    """Preserve on-disk source; the compiled C++ fingerprint is checked independently."""
    paths={p for pattern in ('src/*.cpp','include/physarum/*.hpp','desktop/*.py','analysis/*.py') for p in ROOT.glob(pattern)}
    paths.update(ROOT/p for p in ('CMakeLists.txt','desktop/requirements.txt','analysis/requirements.txt'))
    sources={str(p.relative_to(ROOT).as_posix()):p.read_bytes() for p in sorted(paths)}
    if len(sources)>150 or sum(map(len,sources.values()))>5_000_000:raise ValueError('Source snapshot exceeds supported limits.')
    hashes={name:hashlib.sha256(data).hexdigest() for name,data in sources.items()}
    engine_names=sorted(name for name in sources if name=='CMakeLists.txt' or name.startswith(('src/','include/physarum/')))
    fingerprint=hashlib.sha256(''.join(f'{name}={hashes[name]}\n' for name in engine_names).encode()).hexdigest()
    for name,data in sources.items():
        target=Path(folder)/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    import matplotlib
    return dict(python=platform.python_version(),platform=platform.platform(),numpy=np.__version__,matplotlib=matplotlib.__version__,executable_sha256=sha256_file(ROOT/'build/physarum_mesh'),source_sha256=hashes,source_snapshot=True,engine_source_fingerprint=fingerprint,source_interpretation='Snapshot of source files present at run creation; exact input graph/initialization/forcing and the compiled engine fingerprint are authoritative. Restart the application after editing Python source.')


def archive_source_snapshot(run_folder,target):
    """Deterministic, code-only archive; never includes run data or arbitrary extra files."""
    run_folder=Path(run_folder);manifest=json.loads((run_folder/'scenario.json').read_text())
    if not manifest.get('software',{}).get('source_snapshot'):return
    with Path(target).open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as archive:
        for name,digest in sorted(manifest['software']['source_sha256'].items()):
            data=(run_folder/'source'/name).read_bytes()
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Source snapshot checksum mismatch: '+name)
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0;archive.addfile(info,io.BytesIO(data))


def build_mesh(scene,settings):
    validate_scene(scene);validate_mesh_settings(settings)
    foods=[copy.deepcopy(n) for n in scene['nodes'] if is_food(n)]
    extra=[copy.deepcopy(n) for n in scene['nodes'] if n['kind']=='junction']
    if not 2<=len(foods)<=80:raise ValueError('Choose 2–80 food sources.')
    fixed=foods+extra;points=np.array([[n['x'],n['y']] for n in fixed])
    distances=np.linalg.norm(points[:,None]-points[None,:],axis=2)+np.eye(len(points))*1e6
    if distances.min()<1e-5:raise ValueError('Two selected food/junction coordinates coincide. Select one entry at that location.')
    s=settings['spacing'];lo=points.min(axis=0)-.8;hi=points.max(axis=0)+.8
    domain=scene.get('mesh_bounds_km',scene['geography'].get('design_bounds_km'))
    if domain is not None:lo=np.array(domain[:2],float);hi=np.array(domain[2:],float)
    if np.prod(np.ceil((hi-lo)/[s,s*math.sqrt(3)/2])+2)>7500:raise ValueError('The study area is too large at this mesh spacing. Increase spacing or reduce the area.')
    rng=np.random.default_rng(np.random.SeedSequence([settings['seed'],11]))
    background=[]
    for row,y in enumerate(np.arange(lo[1],hi[1]+s*.1,s*math.sqrt(3)/2)):
        for x in np.arange(lo[0],hi[0]+s*.1,s):background.append([x+(row%2)*s/2,y])
    bg=np.array(background);bg+=rng.uniform(-.2,.2,bg.shape)*s
    near=np.linalg.norm(bg[:,None]-points[None,:],axis=2).min(axis=1)
    bg=bg[near>.12*s]
    local=domain
    if local is not None:bg=bg[(bg[:,0]>=local[0])&(bg[:,0]<=local[2])&(bg[:,1]>=local[1])&(bg[:,1]<=local[3])]
    bounds=scene['geography'].get('coverage_bounds_lat_lon')
    if bounds is not None:
        lon,lat=Transformer.from_crs(27700,4326,always_xy=True).transform(bg[:,0]*1000,bg[:,1]*1000)
        south,west,north,east=bounds;bg=bg[(lat>=south)&(lat<=north)&(lon>=west)&(lon<=east)]
    bg=np.array([p for p in bg if not any(r[0]<=p[0]<=r[2] and r[1]<=p[1]<=r[3] for r in scene['barriers'])])
    if bg.size:points=np.vstack((points,bg))
    if len(points)>5500:raise ValueError('Mesh exceeds 5,500 nodes. Use a larger mesh spacing or a smaller study area.')
    triangles=Triangulation(points[:,0],points[:,1]).triangles
    pairs=set()
    for a,b,c in triangles:
        pairs.update((tuple(sorted((int(a),int(b)))),tuple(sorted((int(b),int(c)))),tuple(sorted((int(c),int(a))))))
    river=[]
    for way in scene['geography']['river']:river.extend(zip(way['xy_km'][:-1],way['xy_km'][1:]))
    river_array=np.asarray(river)
    if len(river_array):rlo=river_array.min(axis=1);rhi=river_array.max(axis=1)
    edges=[]
    for u,v in sorted(pairs):
        a,b=points[u],points[v]
        if any(hits_rectangle(a,b,r) for r in scene['barriers']):continue
        crossing=False
        if len(river_array):
            candidates=np.where(np.all(rhi>=np.minimum(a,b),axis=1)&np.all(rlo<=np.maximum(a,b),axis=1))[0]
            crossing=any(intersects(a,b,*river_array[i]) for i in candidates)
        distance=float(np.linalg.norm(a-b))
        edges.append(dict(id=len(edges),**{'from':u,'to':v},distance_km=distance,length=distance+settings['river_penalty']*crossing,river_crossing=bool(crossing)))
    adjacency=[[] for _ in points]
    for e in edges:adjacency[e['from']].append(e['to']);adjacency[e['to']].append(e['from'])
    seen={0};stack=[0]
    while stack:
        for v in adjacency[stack.pop()]:
            if v not in seen:seen.add(v);stack.append(v)
    if any(i not in seen for i in range(len(foods))):raise ValueError('Restrictions disconnect food sources in the candidate mesh. Remove the restriction or revise the study area.')
    # Discard only demand-free background components, before model initialization.
    kept=sorted(seen);lookup={old:new for new,old in enumerate(kept)}
    nodes=[]
    for old in kept:
        node=copy.deepcopy(fixed[old]) if old<len(fixed) else dict(key=f'mesh-{old}',name=f'Mesh junction {old}',kind='junction',x=float(points[old,0]),y=float(points[old,1]))
        nodes.append(node)
    retained=[]
    for edge in edges:
        if edge['from'] in seen and edge['to'] in seen:
            edge={**edge,'id':len(retained),'from':lookup[edge['from']],'to':lookup[edge['to']]};retained.append(edge)
    if len(retained)>17000:raise ValueError('Mesh exceeds 17,000 edges.')
    return dict(nodes=nodes,edges=retained,food_count=len(foods),discarded_background_nodes=len(points)-len(kept),
        construction='Seeded jittered triangular lattice + exact food/junction vertices; Delaunay triangulation; restricted segments removed before initialization.')


def mesh_demands(scene,settings):
    steps,hold=validate_mesh_settings(settings);foods=[n for n in scene['nodes'] if is_food(n)]
    if settings['demand_mode']=='fixed_pair':
        keys={n['key']:i for i,n in enumerate(foods)}
        if settings['source_id'] not in keys or settings['sink_id'] not in keys:raise ValueError('Choose fixed source and sink from the selected food sites.')
        pair=(keys[settings['source_id']],keys[settings['sink_id']])
        if pair[0]==pair[1]:raise ValueError('Fixed source and sink must differ.')
        return [pair]*(steps+1)
    if settings['demand_mode']=='weighted_pairs':
        rows=validate_pair_weights(scene);keys={n['key']:i for i,n in enumerate(foods)}
        weights=[row['weight'] for row in rows];scale=max(weights);weights=[w/scale for w in weights]
        if any(w==0 for w in weights):raise ValueError('Demand weight range underflows floating-point sampling; rescale or revise the data.')
        rng=random.Random(settings['seed']+101);indices=rng.choices(range(len(rows)),weights=weights,k=steps//hold+1)
        pairs=[(keys[rows[i]['source']],keys[rows[i]['sink']]) for i in indices]
        return [pairs[i//hold] for i in range(steps+1)]
    rng=random.Random(settings['seed']+101);pairs=[tuple(rng.sample(range(len(foods)),2)) for _ in range(steps//hold+1)]
    return [pairs[i//hold] for i in range(steps+1)]


def validate_pair_weights(scene):
    rows=scene.get('weighted_demand',{}).get('pairs',[]);keys={n['key'] for n in scene['nodes'] if is_food(n)}
    if not 1<=len(rows)<=10000:raise ValueError('Import a CSV of 1–10,000 weighted food pairs before using weighted demand.')
    for row in rows:
        if set(row)!={'source','sink','weight'} or row['source'] not in keys or row['sink'] not in keys or row['source']==row['sink']:raise ValueError('Every weighted pair must join two distinct selected food sources. Update the food layout or import a revised CSV.')
        weight=row['weight']
        if isinstance(weight,bool) or not isinstance(weight,(float,int)) or not math.isfinite(weight) or weight<=0:raise ValueError('Demand weights must be positive, finite relative frequencies.')
    return rows


def import_pair_weights(scene,path):
    """CSV weights control pair frequency, not calibrated current or journey volume."""
    path=Path(path)
    if path.stat().st_size>2_000_000:raise ValueError('Demand CSV exceeds 2 MB.')
    foods=[n for n in scene['nodes'] if is_food(n)];aliases={}
    for node in foods:
        for alias in (node['key'],node['name']):
            if alias in aliases and aliases[alias]!=node['key']:raise ValueError('Ambiguous food name; use stable site keys.')
            aliases[alias]=node['key']
    rows=[]
    with path.open(newline='',encoding='utf-8-sig') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=['source','sink','weight']:raise ValueError('CSV header must be exactly source,sink,weight. Use selected food names or stable site keys.')
        for number,row in enumerate(reader,2):
            if len(rows)>=10000:raise ValueError('Demand CSV exceeds 10,000 rows.')
            try:
                source=aliases[row['source'].strip()];sink=aliases[row['sink'].strip()];weight=float(row['weight'])
            except (KeyError,TypeError,ValueError,AttributeError) as error:raise ValueError(f'Invalid demand CSV row {number}: use two selected station names/IDs and a positive weight.') from error
            if None in row:raise ValueError(f'Unexpected extra column at CSV row {number}.')
            rows.append(dict(source=source,sink=sink,weight=weight))
    result=copy.deepcopy(scene);result['weighted_demand']=dict(pairs=rows,filename=path.name,sha256=sha256_file(path),interpretation='User-supplied relative pair frequencies. Weight changes sampling probability; every draw still injects the same I0. No measured-demand claim is inferred from importing a file.')
    validate_pair_weights(result);return result


@dataclass
class MeshRun:
    scene:dict
    settings:dict
    mesh:dict
    times:np.ndarray
    d:np.ndarray
    q:np.ndarray
    p:np.ndarray
    diagnostics:np.ndarray
    pairs:np.ndarray
    folder:Path
    stage_q:np.ndarray|None=None
    stage_p:np.ndarray|None=None
    stage_diagnostics:np.ndarray|None=None
    @property
    def food_count(self):return self.mesh['food_count']


def load_mesh_run(folder):
    folder=Path(folder);manifest=json.loads((folder/'scenario.json').read_text())
    if manifest.get('model')!='Tero_2010_sigmoid_mesh_v1' or manifest.get('schema_version') not in (1,2):raise ValueError('Unsupported tube-model record.')
    scene,settings,mesh=manifest['scene'],manifest['settings'],manifest['mesh'];validate_scene(scene);steps,_=validate_mesh_settings(settings)
    method=settings.get('integrator','euler')
    if method=='heun' and manifest['schema_version']!=2:raise ValueError('Heun stages require tube record schema 2.')
    expected_config=mesh_config(settings)
    if (folder/'inputs/input.cfg').read_text()!=expected_config:raise ValueError('Tube solver configuration disagrees with recorded settings.')
    nodes,edges=mesh['nodes'],mesh['edges'];n,m=len(nodes),len(edges);f=mesh['food_count']
    if not 2<=f<=80 or not f<=n<=5500 or not 1<=m<=17000 or m*(steps+1)>25000000:raise ValueError('Unsupported mesh record size.')
    if mesh_raw_bytes(mesh,settings)>512_000_000:raise ValueError('Tube record exceeds the 512 MB raw-state limit.')
    foods=[node for node in scene['nodes'] if is_food(node)]
    if len(foods)!=f or any(nodes[i]!=foods[i] for i in range(f)):raise ValueError('Food source is not attached to its exact recorded mesh vertex.')
    u=np.array([e['from'] for e in edges],dtype=int);v=np.array([e['to'] for e in edges],dtype=int);length=np.array([e['length'] for e in edges])
    if any(e['id']!=i for i,e in enumerate(edges)) or np.any(u<0) or np.any(v>=n) or np.any(u>=v) or not np.isfinite(length).all() or np.any(length<=0):raise ValueError('Invalid mesh edges.')
    xy=np.array([[node['x'],node['y']] for node in nodes]);physical=np.linalg.norm(xy[u]-xy[v],axis=1)
    if not np.isfinite(xy).all() or not np.allclose(physical,[e['distance_km'] for e in edges],rtol=1e-12,atol=1e-12):raise ValueError('Mesh geometric lengths disagree with coordinates.')
    if not np.allclose(length,physical+settings['river_penalty']*np.array([e['river_crossing'] for e in edges]),rtol=1e-12,atol=1e-12):raise ValueError('Effective mesh costs disagree with recorded assumptions.')
    with (folder/'output/diagnostics.csv').open() as stream:header=stream.readline().strip()
    if header!='step,time,source,sink,conservation_inf,backward_error,scaled_rcond_estimate':raise ValueError('Unexpected tube diagnostics columns.')
    diagnostics=np.loadtxt(folder/'output/diagnostics.csv',skiprows=1,delimiter=',',ndmin=2)
    times=np.arange(steps+1)*settings['dt']
    if diagnostics.shape!=(steps+1,7) or not np.isfinite(diagnostics).all() or not np.array_equal(diagnostics[:,0],np.arange(steps+1)) or not np.allclose(diagnostics[:,1],times,atol=1e-10,rtol=0):raise ValueError('Invalid tube state ordering.')
    pairs=diagnostics[:,2:4].astype(int)
    if not np.array_equal(pairs,diagnostics[:,2:4]) or np.any(pairs<0) or np.any(pairs>=f) or np.any(pairs[:,0]==pairs[:,1]):raise ValueError('Tube demand must use distinct food-source vertices.')
    schedule=np.loadtxt(folder/'inputs/demands.csv',skiprows=1,delimiter=',',ndmin=2)
    if not np.array_equal(schedule,np.column_stack((np.arange(steps+1),pairs))):raise ValueError('Tube record differs from its demand schedule.')
    if not np.array_equal(pairs,np.array(mesh_demands(scene,settings))):raise ValueError('Tube demand protocol differs from recorded settings.')
    arrays=[]
    for name,width in [('D',m),('Q',m),('P',n)]:
        path=folder/'output'/f'{name}.f64'
        if path.stat().st_size!=(steps+1)*width*8:raise ValueError('Truncated tube field: '+name)
        arrays.append(np.memmap(path,dtype='<f8',mode='r',shape=(steps+1,width)))
    d,q,p=arrays
    stage_q=stage_p=stage_diagnostics=None
    if method=='heun':
        stages=[]
        for name,width in [('Q',m),('P',n)]:
            path=folder/'output'/f'stage_{name}.f64'
            if path.stat().st_size!=steps*width*8:raise ValueError('Truncated Heun stage: '+name)
            stages.append(np.memmap(path,dtype='<f8',mode='r',shape=(steps,width)))
        stage_q,stage_p=stages
        with (folder/'output/stage_diagnostics.csv').open() as stream:stage_header=stream.readline().strip()
        if stage_header!=header:raise ValueError('Unexpected Heun stage diagnostics columns.')
        stage_diagnostics=np.loadtxt(folder/'output/stage_diagnostics.csv',skiprows=1,delimiter=',',ndmin=2)
        if stage_diagnostics.shape!=(steps,7) or not np.isfinite(stage_diagnostics).all() or not np.array_equal(stage_diagnostics[:,0],np.arange(steps)) or not np.allclose(stage_diagnostics[:,1],times[1:],atol=1e-10,rtol=0) or not np.array_equal(stage_diagnostics[:,2:4],pairs[:-1]):raise ValueError('Heun stage ordering/held forcing mismatch.')
    initial=np.loadtxt(folder/'inputs/initial.csv',skiprows=1,delimiter=',',ndmin=2)
    if initial.shape!=(m,2) or not np.array_equal(initial[:,0],np.arange(m)) or not np.array_equal(initial[:,1],d[0]):raise ValueError('Initial conductivity record mismatch.')
    lo=settings['initial_conductivity']*(1-settings['initial_noise']);hi=settings['initial_conductivity']*(1+settings['initial_noise'])
    if np.any(d[0]<lo-1e-14) or np.any(d[0]>hi+1e-14):raise ValueError('Initial conductivities disagree with the stated variation range.')
    graph_input=np.loadtxt(folder/'inputs/edges.csv',skiprows=1,delimiter=',',ndmin=2)
    if graph_input.shape!=(m,4) or not np.allclose(graph_input,np.column_stack((np.arange(m),u,v,length)),rtol=0,atol=1e-13):raise ValueError('Mesh input CSV differs from scenario.')
    tolerance=1e-12+1e-10*settings['current']
    if np.any(diagnostics[:,4:6]<0) or np.any(diagnostics[:,4]>tolerance) or np.any(diagnostics[:,5]>1e-12) or np.any(diagnostics[:,6]<1e-14):raise ValueError('Tube solver diagnostics exceed acceptance limits.')
    if stage_diagnostics is not None and (np.any(stage_diagnostics[:,4:6]<0) or np.any(stage_diagnostics[:,4]>tolerance) or np.any(stage_diagnostics[:,5]>1e-12) or np.any(stage_diagnostics[:,6]<1e-14)):raise ValueError('Heun stage diagnostics exceed acceptance limits.')
    for start in range(0,steps+1,64):
        end=min(steps+1,start+64);dd,qq,pp=d[start:end],q[start:end],p[start:end]
        if not np.isfinite(dd).all() or not np.isfinite(qq).all() or not np.isfinite(pp).all() or np.any(dd<=0):raise ValueError('Nonfinite or nonpositive tube state.')
        if np.any(pp[:,0]!=0):raise ValueError('Recorded pressure reference must be exactly node 0.')
        expected=dd/length*(pp[:,u]-pp[:,v])
        if not np.allclose(expected,qq,rtol=2e-10,atol=2e-12):raise ValueError('Tube pressure-flow equation violated.')
        balance=np.zeros((n,end-start))
        np.add.at(balance,u,qq.T);np.add.at(balance,v,-qq.T)
        for j,(source,sink) in enumerate(pairs[start:end]):balance[source,j]-=settings['current'];balance[sink,j]+=settings['current']
        if np.abs(balance).max()>tolerance:raise ValueError('Tube flow does not conserve demand.')
        energy=np.sum(qq*qq*length/dd,axis=1);idx=np.arange(end-start)
        work=settings['current']*(pp[idx,pairs[start:end,0]]-pp[idx,pairs[start:end,1]])
        if not np.allclose(energy,work,rtol=2e-9,atol=2e-10):raise ValueError('Tube dissipation/work identity violated.')
        stop=min(end,steps)
        if start<stop:
            power=np.abs(q[start:stop])**settings['gamma'];predicted=(1-settings['dt'])*d[start:stop]+settings['dt']*power/(1+power)
            if method=='heun':
                if np.any(predicted<=0):raise ValueError('Heun predictor conductivity underflowed.')
                sq,sp=stage_q[start:stop],stage_p[start:stop];batch=stop-start
                if not np.isfinite(sq).all() or not np.isfinite(sp).all() or np.any(sp[:,0]!=0):raise ValueError('Invalid Heun stage pressure/flow.')
                if not np.allclose(sq,predicted/length*(sp[:,u]-sp[:,v]),rtol=2e-10,atol=2e-12):raise ValueError('Heun stage pressure-flow equation violated.')
                balance=np.zeros((n,batch));np.add.at(balance,u,sq.T);np.add.at(balance,v,-sq.T)
                for j,(source,sink) in enumerate(pairs[start:stop]):balance[source,j]-=settings['current'];balance[sink,j]+=settings['current']
                if np.abs(balance).max()>tolerance:raise ValueError('Heun stage does not conserve held demand.')
                energy=np.sum(sq*sq*length/predicted,axis=1);idx=np.arange(batch)
                work=settings['current']*(sp[idx,pairs[start:stop,0]]-sp[idx,pairs[start:stop,1]])
                if not np.allclose(energy,work,rtol=2e-9,atol=2e-10):raise ValueError('Heun stage dissipation/work identity violated.')
                power=np.abs(sq)**settings['gamma'];second=(1-settings['dt'])*predicted+settings['dt']*power/(1+power)
                predicted=.5*d[start:stop]+.5*second
            if not np.allclose(predicted,d[start+1:stop+1],rtol=2e-10,atol=2e-14):raise ValueError(f'Tube conductivity violates the {method} update.')
    checks=json.loads((folder/'checksums.json').read_text())
    expected_paths={'scenario.json','inputs/input.cfg','inputs/edges.csv','inputs/initial.csv','inputs/demands.csv','output/D.f64','output/Q.f64','output/P.f64','output/diagnostics.csv','output/metadata.txt'}
    if method=='heun':expected_paths.update({'output/stage_Q.f64','output/stage_P.f64','output/stage_diagnostics.csv'})
    if set(checks)!=expected_paths:raise ValueError('Incomplete tube checksums.')
    for relative,digest in checks.items():
        if sha256_file(folder/relative)!=digest:raise ValueError('Tube checksum mismatch: '+relative)
    software=manifest.get('software',{})
    if software.get('source_snapshot'):
        sources=software.get('source_sha256',{})
        if not 1<=len(sources)<=150:raise ValueError('Invalid source snapshot index.')
        total=0
        for name,digest in sources.items():
            relative=PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Invalid source snapshot path.')
            path=folder/'source'/relative;total+=path.stat().st_size
            if total>5_000_000 or sha256_file(path)!=digest:raise ValueError('Source snapshot checksum mismatch: '+name)
        engine_names=sorted(name for name in sources if name=='CMakeLists.txt' or name.startswith(('src/','include/physarum/')))
        fingerprint=hashlib.sha256(''.join(f'{name}={sources[name]}\n' for name in engine_names).encode()).hexdigest()
        if fingerprint!=software.get('engine_source_fingerprint'):raise ValueError('Compiled-source fingerprint disagrees with the source snapshot.')
    if 'engine_source_fingerprint' in software:
        metadata=dict(line.split('=',1) for line in (folder/'output/metadata.txt').read_text().splitlines())
        if metadata.get('engine_source_fingerprint')!=software['engine_source_fingerprint']:raise ValueError('Executable does not match the recorded C++ source. Rebuild with CMake before computing this experiment.')
    return MeshRun(scene,settings,mesh,times,d,q,p,diagnostics,pairs,folder,stage_q,stage_p,stage_diagnostics)


def solver_extrema(run):
    records=[run.diagnostics]
    if run.stage_diagnostics is not None:records.append(run.stage_diagnostics)
    return dict(max_conservation=max(float(d[:,4].max()) for d in records),max_backward_error=max(float(d[:,5].max()) for d in records),min_scaled_rcond_estimate=min(float(d[:,6].min()) for d in records))


def compare_mesh_trajectories(a,b):
    """Compare nested recorded time grids only when the graph/forcing/model match."""
    sa,sb=effective_mesh_settings(a.settings),effective_mesh_settings(b.settings)
    if {k:v for k,v in sa.items() if k not in ('dt','integrator')}!={k:v for k,v in sb.items() if k not in ('dt','integrator')}:return None
    if a.mesh!=b.mesh or not np.array_equal(a.d[0],b.d[0]):return None
    coarse,fine=(a,b) if sa['dt']>=sb['dt'] else (b,a)
    ratio=round(coarse.settings['dt']/fine.settings['dt'])
    if ratio<1 or not math.isclose(ratio*fine.settings['dt'],coarse.settings['dt'],rel_tol=0,abs_tol=1e-12):return None
    if len(fine.times)!=ratio*(len(coarse.times)-1)+1 or not np.allclose(coarse.times,fine.times[::ratio],rtol=0,atol=1e-10):return None
    if not np.array_equal(fine.pairs,coarse.pairs[np.arange(len(fine.times))//ratio]):return None
    differences=[];sum_squares=0.;count=0
    for start in range(0,len(coarse.times),64):
        end=min(start+64,len(coarse.times));delta=coarse.d[start:end]-fine.d[start*ratio:end*ratio:ratio]
        differences.extend(np.max(np.abs(delta),axis=1).tolist());sum_squares+=float(np.sum(delta*delta));count+=delta.size
    return dict(coarse_dt=coarse.settings['dt'],fine_dt=fine.settings['dt'],method_a=sa['integrator'],method_b=sb['integrator'],max_D_difference=max(differences),final_D_max_difference=differences[-1],rms_D_difference=math.sqrt(sum_squares/count),times=coarse.times.tolist(),max_D_difference_by_time=differences,interpretation='Matched graph, initial values and full held forcing. A finite pairwise numerical comparison, not an exact error estimate or proof of converged topology.')


def run_mesh_experiment(scene,settings,root=None,cancel=None):
    scene,settings=copy.deepcopy(scene),copy.deepcopy(settings);steps,_=validate_mesh_settings(settings);mesh=build_mesh(scene,settings)
    if len(mesh['edges'])*(steps+1)>25000000:raise ValueError('This mesh/time-step combination creates too much recorded data; increase spacing or dt.')
    if mesh_raw_bytes(mesh,settings)>512_000_000:raise ValueError('This experiment exceeds 512 MB of raw states; increase dt or mesh spacing.')
    pairs=mesh_demands(scene,settings);m=len(mesh['edges']);rng=np.random.default_rng(np.random.SeedSequence([settings['seed'],23]))
    initial=settings['initial_conductivity']*(1+rng.uniform(-settings['initial_noise'],settings['initial_noise'],m))
    folder=Path(root or ROOT/'results/mesh_runs')/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]);inputs=folder/'inputs';inputs.mkdir(parents=True)
    manifest=dict(schema_version=2 if 'integrator' in settings else 1,model='Tero_2010_sigmoid_mesh_v1',scene=scene,settings=settings,mesh=mesh,
        protocol=f"Steady pressure solve Q=D/L×dp; simultaneous sigmoid {settings.get('integrator','euler')} adaptation; recorded food-pair forcing.",
        differences='Our mesh generation, initial uniform noise, integrator and demand switching interval are documented choices. No exact Tokyo replication or biological growth claim.',
        geometry='Exact food coordinates are mesh vertices; tube geometry is the actual piecewise-linear mesh, without cosmetic curve smoothing.',
        source='https://doi.org/10.1126/science.1177894')
    executable=ROOT/'build/physarum_mesh'
    manifest['software']=capture_source_snapshot(folder)
    (folder/'scenario.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    (inputs/'input.cfg').write_text(mesh_config(settings))
    for name,header,rows in [('edges.csv',['edge','from','to','length'],[(e['id'],e['from'],e['to'],e['length']) for e in mesh['edges']]),('initial.csv',['edge','conductivity'],list(enumerate(initial))),('demands.csv',['step','source','sink'],[(i,*pair) for i,pair in enumerate(pairs)])]:
        with (inputs/name).open('w',newline='') as stream:writer=csv.writer(stream,lineterminator='\n');writer.writerow(header);writer.writerows(rows)
    command=[str(executable),str(inputs/'input.cfg'),str(inputs/'edges.csv'),str(len(mesh['nodes'])),str(inputs/'initial.csv'),str(inputs/'demands.csv'),str(folder/'output')]
    try:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);elapsed=0
        while True:
            try:stdout,stderr=process.communicate(timeout=.2);break
            except subprocess.TimeoutExpired:
                elapsed+=.2
                if (cancel is not None and cancel.is_set()) or elapsed>240:
                    process.terminate()
                    try:process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:process.kill();process.communicate()
                    raise ValueError('Tube experiment cancelled or timed out.')
        (folder/'engine.log').write_text(stdout+stderr)
        if process.returncode:raise ValueError(stderr.strip())
        checks={str(path.relative_to(folder)):sha256_file(path) for directory in (inputs,folder/'output') for path in directory.iterdir() if path.is_file()};checks['scenario.json']=sha256_file(folder/'scenario.json')
        (folder/'checksums.json').write_text(json.dumps(checks,indent=2)+'\n')
        return load_mesh_run(folder)
    except Exception as error:
        (folder/'failure.txt').write_text(str(error));raise ValueError(f'{error}\nInputs and any partial output retained: {folder}') from error


def mesh_metrics(run,index,cutoff=DEFAULT_CUTOFF,routes=False):
    if not math.isfinite(cutoff) or cutoff<=0:raise ValueError('Conductivity cutoff must be positive and finite.')
    nodes,edges=run.mesh['nodes'],run.mesh['edges'];n=len(nodes);f=run.food_count
    selected=np.flatnonzero(run.d[index]>=cutoff);adj=[[] for _ in nodes]
    length=0.
    for k in selected:
        e=edges[k];u,v=e['from'],e['to'];adj[u].append((v,int(k)));adj[v].append((u,int(k)));length+=e['distance_km']
    disc=np.full(n,-1,dtype=int);low=disc.copy();parent=disc.copy();pe=disc.copy();component=disc.copy();counts=np.zeros(n,dtype=int);counts[:f]=1
    clock=0;components=[];bridges=[]
    for root in range(n):
        if disc[root]>=0:continue
        cid=len(components);disc[root]=low[root]=clock;clock+=1;component[root]=cid;stack=[(root,0)];local=[]
        while stack:
            u,j=stack[-1]
            if j<len(adj[u]):
                v,k=adj[u][j];stack[-1]=(u,j+1)
                if k==pe[u]:continue
                if disc[v]<0:
                    parent[v]=u;pe[v]=k;disc[v]=low[v]=clock;clock+=1;component[v]=cid;stack.append((v,0))
                else:low[u]=min(low[u],disc[v])
            else:
                stack.pop()
                if parent[u]>=0:
                    v=parent[u];counts[v]+=counts[u];low[v]=min(low[v],low[u])
                    if low[u]>disc[v]:local.append((pe[u],counts[u]))
        total=int(counts[root]);components.append(total)
        bridges.extend((k,int(side),total) for k,side in local)
    pair_total=f*(f-1)/2;connected_pairs=sum(k*(k-1)/2 for k in components)
    full=max(components)==f;cut_length=sum(edges[k]['distance_km'] for k,side,total in bridges if 0<side<total)
    pair_losses=[side*(total-side) for _,side,total in bridges]
    weighted_pair_loss=sum(edges[k]['distance_km']*side*(total-side) for k,side,total in bridges)
    result=dict(cutoff=cutoff,retained_segments=len(selected),length_km=float(length),largest_food_component=max(components),
        connected_pair_fraction=connected_pairs/pair_total,food_without_retained_tube=sum(not adj[i] for i in range(f)),
        food_component_sizes=[components[component[i]] for i in range(f)],
        all_food_connected=full,single_break_survival=max(0.,min(1.,1-cut_length/length)) if full and length>0 else 0.,
        critical_bridge_length_km=float(cut_length),
        expected_connected_pair_fraction_after_break=max(0.,min(1.,connected_pairs/pair_total-weighted_pair_loss/(length*pair_total))) if length>0 else connected_pairs/pair_total,
        worst_break_connected_pair_fraction=max(0.,(connected_pairs-max(pair_losses,default=0))/pair_total),
        volume_proxy=float(np.sum(np.sqrt(run.d[index])*np.array([e['distance_km'] for e in edges]))))
    if run.p is not None:
        source,sink=run.pairs[index];drop=float(run.p[index,source]-run.p[index,sink])
        result['current_pair_pressure_drop_model_units']=drop
        result['current_pair_dissipation_model_units']=float(run.settings['current']*drop)
    if routes:
        distances=[];straight=[];xy=np.array([[node['x'],node['y']] for node in nodes[:f]])
        for source in range(f):
            best=np.full(n,np.inf);best[source]=0.;queue=[(0.,source)]
            while queue:
                distance,u=heapq.heappop(queue)
                if distance>best[u]:continue
                for v,k in adj[u]:
                    candidate=distance+edges[k]['distance_km']
                    if candidate<best[v]:best[v]=candidate;heapq.heappush(queue,(candidate,v))
            for sink in range(source+1,f):
                if math.isfinite(best[sink]):distances.append(best[sink]);straight.append(float(np.linalg.norm(xy[source]-xy[sink])))
        result['mean_route_km']=float(np.mean(distances)) if full else None
        result['mean_route_direct_ratio']=float(np.mean(np.array(distances)/straight)) if full else None
        # A terminal-only Euclidean MST is a reference, not a lower bound with Steiner points.
        matrix=np.linalg.norm(xy[:,None]-xy[None,:],axis=2);chosen=np.zeros(f,dtype=bool);distance=np.full(f,np.inf);distance[0]=0;mst=0.
        for _ in range(f):
            v=int(np.argmin(np.where(chosen,np.inf,distance)));mst+=distance[v];chosen[v]=True;distance=np.minimum(distance,matrix[v])
        result['terminal_mst_km']=mst;result['length_over_terminal_mst']=length/mst
    return result
