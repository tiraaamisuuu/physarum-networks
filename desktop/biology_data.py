"""Inputs and audited records for the exploratory migration benchmark.

The cooperative calcium variant and finite element/time discretization are
explicit modelling choices. This is not a calibrated biological replica.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import subprocess
import uuid
import numpy as np
from matplotlib.path import Path as MplPath
from matplotlib.tri import Triangulation
try:
    from .mesh_data import capture_source_snapshot
except ImportError:
    from mesh_data import capture_source_snapshot
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_BIOLOGY=dict(arena='snake',spacing=.5,seed=42,duration=1280.,dt=.02,hill=4,feedback=.01,tau_front=2.,save_interval=8.)
POLYGON=np.array([(0,10),(5,10),(5,0),(20,0),(20,10),(25,10),(25,0),(40,0),(40,5),(30,5),(30,15),(15,15),(15,5),(10,5),(10,15),(0,15)],float)
RECTANGLES=np.array([(0,10,10,15),(5,0,10,15),(5,0,20,5),(15,0,20,15),(15,10,30,15),(25,0,30,15),(25,0,40,5)],float)

def validate_biology(settings):
    if set(settings)!=set(DEFAULT_BIOLOGY):raise ValueError('Incomplete biological settings.')
    if settings['arena'] not in ('snake','straight'):raise ValueError('Unknown corridor arena.')
    for key,low,high in [('spacing',.35,1.),('duration',8,1600),('dt',.005,.04),('feedback',0,.1),('tau_front',2,40),('save_interval',.1,40)]:
        x=settings[key]
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not low<=x<=high:raise ValueError(f'{key} must be in [{low}, {high}].')
    if settings['hill'] not in (1,4) or isinstance(settings['hill'],bool):raise ValueError('Hill exponent must be 1 (printed control) or 4 (cooperative variant).')
    if isinstance(settings['seed'],bool) or not isinstance(settings['seed'],int) or not 0<=settings['seed']<2**31:raise ValueError('Invalid mesh seed.')
    for key in ('duration','save_interval'):
        if not math.isclose(round(settings[key]/settings['dt'])*settings['dt'],settings[key],abs_tol=1e-8):raise ValueError(f'{key} must be a multiple of dt.')
    if settings['duration']/settings['dt']>160000 or settings['save_interval']>settings['duration']:raise ValueError('Biological record exceeds supported steps/interval.')

def geometry(arena):
    if arena=='snake':return POLYGON.copy(),RECTANGLES.copy()
    return np.array([(0,0),(40,0),(40,5),(0,5)],float),np.array([(0,0,40,5)],float)

def inside(points,rectangles):
    p=np.asarray(points);r=rectangles
    return ((p[:,None,0]>=r[None,:,0]-1e-10)&(p[:,None,0]<=r[None,:,2]+1e-10)&(p[:,None,1]>=r[None,:,1]-1e-10)&(p[:,None,1]<=r[None,:,3]+1e-10)).any(axis=1)

def segment_inside(a,b,rectangles):
    # Exact interval partition for an orthogonal union: no subpixel wall crossings.
    t=[0.,1.];delta=b-a
    for axis in (0,1):
        if abs(delta[axis])>1e-14:
            cuts=((rectangles[:,[axis,axis+2]].ravel()-a[axis])/delta[axis]);t.extend(cuts[(cuts>0)&(cuts<1)])
    t=np.unique(t);return inside(a+(.5*(t[:-1]+t[1:]))[:,None]*delta,rectangles).all()

def make_biology_mesh(settings):
    validate_biology(settings);h=settings['spacing'];polygon,rectangles=geometry(settings['arena']);rng=np.random.default_rng(settings['seed']);boundary=[]
    for a,b in zip(polygon,np.roll(polygon,-1,axis=0)):
        count=int(np.ceil(np.linalg.norm(b-a)/h));boundary.extend(a+(b-a)*np.arange(count)[:,None]/count)
    boundary=np.asarray(boundary);xy=np.array([(x+(row%2)*h/2,y) for row,y in enumerate(np.arange(h/2,polygon[:,1].max(),h*np.sqrt(3)/2)) for x in np.arange(h/2,40,h)])
    xy+=rng.uniform(-.12*h,.12*h,xy.shape);xy=xy[MplPath(polygon).contains_points(xy)]
    xy=xy[np.min(np.linalg.norm(xy[:,None,:]-boundary[None,:,:],axis=2),axis=1)>.9*h]
    xy=np.vstack([boundary,xy]);raw=Triangulation(*xy.T).triangles
    triangles=np.array([t for t in raw if all(segment_inside(xy[t[i]],xy[t[(i+1)%3]],rectangles) for i in range(3))])
    mass=np.zeros(len(xy));weights={}
    for t in triangles:
        p=xy[t];area=abs(np.linalg.det(np.array([p[1]-p[0],p[2]-p[0]])))/2
        if area<=1e-12:raise ValueError('Degenerate biological triangle.')
        mass[t]+=area/3
        for i in range(3):
            a,b=int(t[(i+1)%3]),int(t[(i+2)%3]);key=tuple(sorted((a,b)));weights[key]=weights.get(key,0)+np.dot(xy[a]-p[i],xy[b]-p[i])/(4*area)
    if min(mass)<=0 or min(weights.values())<0:raise ValueError('This mesh lacks positive finite-element weights; try another seed or spacing. No weights were clipped.')
    expected=350 if settings['arena']=='snake' else 200
    if not math.isclose(mass.sum(),expected,abs_tol=1e-8):raise ValueError('Mesh does not cover the entire corridor.')
    edges=np.array([(a,b,np.linalg.norm(xy[a]-xy[b]),w) for (a,b),w in sorted(weights.items())])
    # Explicitly reject disconnected domains, including zero-weight diffusion islands.
    neighbours=[[] for _ in xy]
    for a,b,_,w in edges:
        if w>0:neighbours[int(a)].append(int(b));neighbours[int(b)].append(int(a))
    seen={0};stack=[0]
    while stack:
        for b in neighbours[stack.pop()]:
            if b not in seen:seen.add(b);stack.append(b)
    if len(seen)!=len(xy):raise ValueError('Disconnected biological mesh.')
    inoculum=(xy[:,0]>=39-1e-10)&(xy[:,1]<=5+1e-10)
    if not inoculum.any():raise ValueError('Mesh misses the inoculum.')
    return dict(xy=xy,mass=mass,edges=edges,triangles=triangles,inoculum=inoculum,polygon=polygon)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_biology_inputs(folder,mesh):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    np.savetxt(folder/'nodes.csv',np.column_stack([np.arange(len(mesh['xy'])),mesh['xy'],mesh['mass'],mesh['inoculum'].astype(int)]),delimiter=',',header='id,x,y,mass,inoculum',comments='',fmt='%.17g')
    np.savetxt(folder/'edges.csv',np.column_stack([np.arange(len(mesh['edges'])),mesh['edges']]),delimiter=',',header='id,from,to,length,weight',comments='',fmt='%.17g')
    np.savetxt(folder/'triangles.csv',mesh['triangles'],delimiter=',',header='a,b,c',comments='',fmt='%d')

def run_biology(settings=None,progress=None,cancelled=None,folder=None):
    settings=dict(DEFAULT_BIOLOGY if settings is None else settings);mesh=make_biology_mesh(settings)
    folder=Path(folder) if folder else ROOT/'results/biology_runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    if folder.exists() and any(folder.iterdir()):raise ValueError('Biological output must be new/empty.')
    write_biology_inputs(folder,mesh);software=capture_source_snapshot(folder);executable=ROOT/'build/physarum_biology';software['executable_sha256']=sha(executable)
    manifest=dict(schema=1,settings=settings,software=software,source='Schenz et al. 2017, DOI 10.1088/1361-6463/aa88e9; cooperative4 restores the Smith & Saldana 1992 Hill exponent as an explicit variant.',discretization='Lumped P1 FEM, no-flux boundary; split RK4 reaction and backward-Euler diffusion; frozen-coefficient Crank–Nicolson fluid; exponential vein update. Overall first order, uncalibrated model units.',status='computing')
    (folder/'scenario.json').write_text(json.dumps(manifest,indent=2)+'\n')
    candidate=np.flatnonzero(mesh['inoculum']);probe=int(candidate[np.argmin(np.linalg.norm(mesh['xy'][candidate]-[39.5,2.5],axis=1))]);args=[str(executable),str(folder/'nodes.csv'),str(folder/'edges.csv')]+[str(settings[k]) for k in ('duration','dt','hill','feedback','tau_front','save_interval')]+[str(probe),str(folder/'raw')]
    with (folder/'engine.log').open('w') as log:
        process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        try:
            for line in process.stdout:
                log.write(line);log.flush()
                if cancelled and cancelled():process.terminate();raise RuntimeError('Biological experiment cancelled; partial files remain saved.')
                if line.startswith('PROGRESS ') and progress:progress(float(line.split()[1])/settings['duration'])
            if process.wait()!=0:raise RuntimeError((folder/'engine.log').read_text()[-3000:])
        finally:
            if process.poll() is None:process.terminate();process.wait()
            process.stdout.close()
    engine=json.loads((folder/'raw/engine.json').read_text())
    if engine['source_fingerprint']!=software['engine_source_fingerprint']:raise ValueError('Biology executable is stale; rebuild before computing.')
    manifest['files']={str(p.relative_to(folder)):sha(p) for p in sorted(folder.glob('*.csv'))+sorted((folder/'raw').glob('*'))};manifest['status']='complete'
    (folder/'scenario.json').write_text(json.dumps(manifest,indent=2)+'\n');return load_biology(folder)

def load_biology(folder):
    folder=Path(folder);manifest=json.loads((folder/'scenario.json').read_text());settings=manifest['settings'];validate_biology(settings)
    if manifest.get('schema')!=1 or manifest.get('status')!='complete':raise ValueError('Not a complete biological experiment.')
    expected={'nodes.csv','edges.csv','triangles.csv'}|{'raw/'+n for n in ('engine.json','history.csv','probe.csv')}|{'raw/'+n+'.f64' for n in ('c','phi','u','v','w','p','q','d')}
    if set(manifest.get('files',{}))!=expected:raise ValueError('Biological manifest file set mismatch.')
    for name,digest in manifest['files'].items():
        if sha(folder/name)!=digest:raise ValueError('Biological checksum mismatch: '+name)
    sources=manifest['software']['source_sha256']
    for name,digest in sources.items():
        if Path(name).is_absolute() or '..' in Path(name).parts or not name.startswith(('src/','include/','desktop/','analysis/','CMakeLists.txt')):raise ValueError('Invalid source snapshot path.')
        if sha(folder/'source'/name)!=digest:raise ValueError('Biological source checksum mismatch: '+name)
    fingerprint=hashlib.sha256(''.join(f'{name}={sources[name]}\n' for name in sorted(sources) if name=='CMakeLists.txt' or name.startswith(('src/','include/physarum/'))).encode()).hexdigest()
    engine=json.loads((folder/'raw/engine.json').read_text())
    if fingerprint!=engine['source_fingerprint'] or fingerprint!=manifest['software']['engine_source_fingerprint']:raise ValueError('Biology compiled source mismatch.')
    nodes=np.loadtxt(folder/'nodes.csv',delimiter=',',skiprows=1,ndmin=2);edges=np.loadtxt(folder/'edges.csv',delimiter=',',skiprows=1,ndmin=2);triangles=np.loadtxt(folder/'triangles.csv',delimiter=',',skiprows=1,dtype=int,ndmin=2)
    n,e,frames=engine['nodes'],engine['edges'],engine['frames']
    if n!=len(nodes) or e!=len(edges) or nodes.shape[1]!=5 or edges.shape[1]!=5 or not np.array_equal(nodes[:,0],np.arange(n)) or not np.array_equal(edges[:,0],np.arange(e)):raise ValueError('Biological mesh dimensions mismatch.')
    if any(engine[k]!=settings[k] for k in ('dt','hill','feedback','tau_front')):raise ValueError('Biology engine parameters mismatch.')
    if not np.isfinite(nodes).all() or not np.isfinite(edges).all() or np.any(nodes[:,3]<=0) or np.any(edges[:,3]<=0) or np.any(edges[:,4]<0) or not np.isin(nodes[:,4],[0,1]).all():raise ValueError('Invalid biological mesh values.')
    if not np.array_equal(edges[:,1:3],edges[:,1:3].astype(int)) or edges[:,1:3].min()<0 or edges[:,1:3].max()>=n or triangles.min()<0 or triangles.max()>=n:raise ValueError('Invalid biological mesh indices.')
    if not np.allclose(np.linalg.norm(nodes[edges[:,1].astype(int),1:3]-nodes[edges[:,2].astype(int),1:3],axis=1),edges[:,3],atol=1e-12):raise ValueError('Biological edge lengths mismatch.')
    fields={}
    for name in ('c','phi','u','v','w','p','q','d'):
        count=e if name in ('q','d') else n;path=folder/'raw'/(name+'.f64')
        if path.stat().st_size!=8*frames*count:raise ValueError('Biological state dimensions mismatch.')
        fields[name]=np.memmap(path,dtype='<f8',mode='r',shape=(frames,count))
        if not np.isfinite(fields[name]).all():raise ValueError('Non-finite biological data.')
    if any(fields[k].min() < -1e-10 for k in ('u','v','w','d')) or np.any(np.diff(fields['w'],axis=0)<-1e-10):raise ValueError('Biological positivity/body accumulation mismatch.')
    seed=nodes[:,4].astype(bool);seed_edge=seed[edges[:,1].astype(int)]|seed[edges[:,2].astype(int)]
    initial=dict(c=seed.astype(float),phi=np.zeros(n),u=np.full(n,3.),v=seed.astype(float),w=np.zeros(n),p=np.zeros(n),q=np.zeros(e),d=.1*seed_edge)
    for name,values in initial.items():
        if not np.array_equal(fields[name][0],values):raise ValueError('Biological initial state mismatch: '+name)
    outside=.5*(fields['w'][:,edges[:,1].astype(int)]+fields['w'][:,edges[:,2].astype(int)])<=1
    if np.any(fields['d'][outside & ~seed_edge[None,:]]!=0):raise ValueError('Vein reinforcement occurred outside the body gate.')
    history=np.genfromtxt(folder/'raw/history.csv',delimiter=',',names=True,ndmin=1);probe=np.genfromtxt(folder/'raw/probe.csv',delimiter=',',names=True,ndmin=1)
    steps=round(settings['duration']/settings['dt']);stride=round(settings['save_interval']/settings['dt']);indices=np.unique(np.r_[np.arange(0,steps+1,stride),steps])
    if len(history)!=frames or not np.allclose(history['time'],indices*settings['dt'],atol=1e-10,rtol=0) or len(probe)!=steps+1 or not np.allclose(probe['time'],np.arange(steps+1)*settings['dt'],atol=1e-10,rtol=0):raise ValueError('Biological recording times mismatch.')
    if not np.isfinite(history.view(float)).all() or not np.isfinite(probe.view(float)).all():raise ValueError('Non-finite biology diagnostics.')
    if max(probe['fluid_residual'])>1e-7 or max(probe['energy_defect'])>1e-9:raise ValueError('Biological fluid balance failed.')
    body=(fields['w']>1)@nodes[:,3];length=(fields['d']>=1)@edges[:,3]
    if not np.allclose(body,history['body_area'],atol=1e-8) or not np.allclose(length,history['vein_length'],atol=1e-8):raise ValueError('Biological summary disagrees with raw fields.')
    return dict(folder=folder,manifest=manifest,settings=settings,engine=engine,xy=nodes[:,1:3],mass=nodes[:,3],inoculum=nodes[:,4].astype(bool),edges=edges[:,1:],triangles=triangles,fields=fields,history=history,probe=probe)
