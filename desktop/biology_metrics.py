"""Geometric vein diagnostics; footprint occupancy never substitutes for tubes."""
import numpy as np
try:
    from .biology_data import geometry
except ImportError:
    from biology_data import geometry


def vein_metrics(xy,edges,conductivity,inoculum,arena,cutoff=1.):
    xy=np.asarray(xy);edges=np.asarray(edges);d=np.asarray(conductivity);seed=np.asarray(inoculum,dtype=bool)
    if len(d)!=len(edges) or len(seed)!=len(xy) or not np.isfinite(d).all() or np.any(d<0) or not np.isfinite(cutoff) or cutoff<=0:raise ValueError('Invalid vein diagnostic inputs.')
    endpoints=edges[:,:2].astype(int);active=d>=cutoff;adj=[[] for _ in xy]
    for a,b in endpoints[active]:adj[a].append(int(b));adj[b].append(int(a))
    reachable=set(np.flatnonzero(seed));stack=list(reachable)
    while stack:
        for b in adj[stack.pop()]:
            if b not in reachable:reachable.add(b);stack.append(b)
    source_edges=active & np.array([int(a) in reachable and int(b) in reachable for a,b in endpoints])
    unused=set(endpoints[active].ravel());components=0
    while unused:
        components+=1;stack=[int(unused.pop())]
        while stack:
            for b in adj[stack.pop()]:
                if b in unused:unused.remove(b);stack.append(b)
    length=float(edges[active,2].sum());source_length=float(edges[source_edges,2].sum())
    if not active.any():return dict(cutoff=float(cutoff),components=0,length=0.,inoculum_attached_length=0.,inoculum_attached_fraction=None,mean_wall_clearance=None,near_wall_length_fraction=None)
    # Midpoint diagnostic, not an inferred image skeleton or fitted vein path.
    points=xy[endpoints[active]].mean(axis=1);polygon,_=geometry(arena);a=polygon;b=np.roll(polygon,-1,axis=0);v=b-a
    projection=np.clip(((points[:,None,:]-a[None,:,:])*v[None,:,:]).sum(axis=2)/(v*v).sum(axis=1),0,1)
    distance=np.linalg.norm(points[:,None,:]-(a[None,:,:]+projection[:,:,None]*v[None,:,:]),axis=2).min(axis=1);weights=edges[active,2]
    return dict(cutoff=float(cutoff),components=components,length=length,inoculum_attached_length=source_length,inoculum_attached_fraction=source_length/length,mean_wall_clearance=float(np.dot(weights,distance)/length),near_wall_length_fraction=float(weights[distance<=.5].sum()/length))
