"""Path inspection on the actual retained mesh, with no invented links."""
import heapq
import numpy as np

def retained_route(run,index,start,end,cutoff):
    if not np.isfinite(cutoff) or cutoff<=0 or not 0<=index<len(run.times):raise ValueError('Choose a valid recorded frame and positive cutoff.')
    if start==end:raise ValueError('Choose two different food sites.')
    if not 0<=start<run.food_count or not 0<=end<run.food_count:raise ValueError('Choose sites in this recorded run.')
    adj=[[] for _ in run.mesh['nodes']]
    for k,e in enumerate(run.mesh['edges']):
        if run.d[index,k]>=cutoff:
            adj[e['from']].append((e['to'],e['distance_km'],k));adj[e['to']].append((e['from'],e['distance_km'],k))
    distance={start:0.};previous={};queue=[(0.,start)]
    while queue:
        cost,u=heapq.heappop(queue)
        if cost!=distance[u]:continue
        if u==end:break
        for v,length,k in adj[u]:
            value=cost+length
            if value<distance.get(v,float('inf')):distance[v]=value;previous[v]=(u,k);heapq.heappush(queue,(value,v))
    if end not in distance:return None
    nodes=[end];edges=[]
    while nodes[-1]!=start:
        u,k=previous[nodes[-1]];nodes.append(u);edges.append(k)
    nodes.reverse();edges.reverse()
    xy=np.array([[n['x'],n['y']] for n in run.mesh['nodes']])
    return dict(nodes=nodes,edges=edges,length_km=distance[end],direct_km=float(np.linalg.norm(xy[start]-xy[end])),foods=[run.mesh['nodes'][i]['name'] for i in nodes if i<run.food_count])
