"""Reversible experiment design; user points never masquerade as TfL stations."""
import copy
import math
import uuid
from pyproj import Transformer
try:
    from .spatial_data import default_scene,validate_scene,is_food
except ImportError:
    from spatial_data import default_scene,validate_scene,is_food

_TO_GEO=Transformer.from_crs(27700,4326,always_xy=True)
_TO_GRID=Transformer.from_crs(4326,27700,always_xy=True)

def is_sandbox(scene):return scene['geography'].get('coordinate_system')=='local_km'
def scene_title(scene):return 'Sandbox' if is_sandbox(scene) else 'London'
def scene_credit(scene):return 'User-designed layout · local distances in km' if is_sandbox(scene) else ('User food sites + TfL station coordinates · © OpenStreetMap contributors' if any(n['kind']=='food' for n in scene['nodes']) else 'TfL station coordinates · © OpenStreetMap contributors')
def food_nodes(scene):return [n for n in scene['nodes'] if is_food(n)]

def design_bounds(scene):
    if is_sandbox(scene):return scene['geography']['design_bounds_km']
    south,west,north,east=scene['geography']['coverage_bounds_lat_lon'];points=[_TO_GRID.transform(lon,lat) for lon,lat in ((west,south),(west,north),(east,south),(east,north))]
    return [min(p[0] for p in points)/1000,min(p[1] for p in points)/1000,max(p[0] for p in points)/1000,max(p[1] for p in points)/1000]

def sandbox_scene():
    return dict(schema_version=1,name='Free network sandbox',nodes=[],barriers=[],geography=dict(coordinate_system='local_km',design_bounds_km=[0.,0.,16.,10.],station_catalog=[],river=[],elevation=dict(x=[0.,16.],y=[0.,10.],metres=[[0.,0.],[0.,0.]])))

def edit_food(scene,key=None,*,x=None,y=None,name=None):
    """Return a validated copy; stable IDs survive move/rename. No record mutation."""
    result=copy.deepcopy(scene)
    if key is None:
        if len(food_nodes(result))>=80:raise ValueError('Use at most 80 food sites.')
        number=1;names={n['name'] for n in result['nodes']}
        while f'Food {number:02d}' in names:number+=1
        node=dict(key='food-'+uuid.uuid4().hex[:12],kind='food',name=name or f'Food {number:02d}',x=x,y=y,provenance='User-placed food site; not an official station.')
        result['nodes'].append(node)
    else:
        node=next((n for n in result['nodes'] if n['key']==key),None)
        if node is None:raise ValueError('That food site is no longer in the design.')
        if node['kind']!='food':raise ValueError('Official station names and coordinates stay fixed. Add a custom food site to try another location.')
        if x is not None:node['x']=x
        if y is not None:node['y']=y
        if name is not None:node['name']=name.strip()
    for coordinate in ('x','y'):
        if isinstance(node[coordinate],bool) or not isinstance(node[coordinate],(int,float)) or not math.isfinite(node[coordinate]):raise ValueError('Food coordinates must be finite numbers.')
        node[coordinate]=float(node[coordinate])
    if not isinstance(node['name'],str) or not 1<=len(node['name'].strip())<=80:raise ValueError('Use a food name of 1–80 characters.')
    node['name']=node['name'].strip()
    if is_sandbox(result):
        x0,y0,x1,y1=result['geography']['design_bounds_km']
        if not x0<=node['x']<=x1 or not y0<=node['y']<=y1:raise ValueError('Place food inside the sandbox boundary.')
    else:
        lon,lat=_TO_GEO.transform(node['x']*1000,node['y']*1000);node.update(lat=float(lat),lon=float(lon));result['mesh_bounds_km']=design_bounds(result)
    if any(n['key']!=node['key'] and n['name'].strip().casefold()==node['name'].casefold() for n in result['nodes']):raise ValueError('Another site already uses that name.')
    if any(a<=node['x']<=c and b<=node['y']<=d for a,b,c,d in result['barriers']):raise ValueError('Food cannot be placed inside a blocked area.')
    if any(other['key']!=node['key'] and math.hypot(node['x']-other['x'],node['y']-other['y'])<.001 for other in result['nodes']):raise ValueError('Food sites must be at least one metre apart.')
    validate_scene(result);return result,node['key']

def sandbox_example():
    scene=sandbox_scene();scene,a=edit_food(scene,x=2.,y=5.,name='West food');scene,b=edit_food(scene,x=14.,y=5.,name='East food');scene['nodes'][0]['key']='sandbox-west';scene['nodes'][1]['key']='sandbox-east';scene['name']='Sandbox: route around a blocked area';scene['barriers']=[[7.,2.,9.,8.]];return scene

class DesignHistory:
    def __init__(self,limit=50):self.undo_stack=[];self.redo_stack=[];self.limit=limit
    def push(self,scene):
        self.undo_stack.append(copy.deepcopy(scene));self.undo_stack=self.undo_stack[-self.limit:];self.redo_stack.clear()
    def undo(self,current):
        if not self.undo_stack:return current
        self.redo_stack.append(copy.deepcopy(current));return self.undo_stack.pop()
    def redo(self,current):
        if not self.redo_stack:return current
        self.undo_stack.append(copy.deepcopy(current));return self.redo_stack.pop()
