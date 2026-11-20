"""Readable labels use display-space placement only; food coordinates stay exact."""
import textwrap
from matplotlib import patheffects

HUBS=("King's Cross",'Paddington','Waterloo','Victoria','Liverpool Street','London Bridge','Stratford','Canary Wharf','Oxford Circus','Bank','Westminster','Baker Street','Hammersmith','Elephant','Earl')

class FoodLabels:
    def __init__(self,axis,nodes,mode='key'):
        self.axis=axis;self.nodes=nodes;self.mode=mode;self.priority=[];self.signature=None;self.annotations=[]
        for node in nodes:
            label='\n'.join(textwrap.wrap(node['name'],24))
            a=axis.annotate(label,(node['x'],node['y']),xytext=(6,5),textcoords='offset points',fontsize=7.5,color='#263d38',zorder=8,annotation_clip=True)
            a.set_path_effects([patheffects.withStroke(linewidth=2.5,foreground='#fafbf8')]);a.set_in_layout(False);a.set_visible(False);self.annotations.append(a)
        self.connection=axis.figure.canvas.mpl_connect('draw_event',self.draw)
    def disconnect(self):self.axis.figure.canvas.mpl_disconnect(self.connection)
    def draw(self,event):
        if self.mode=='none':return
        box=self.axis.bbox;signature=tuple(round(v,2) for v in (*self.axis.get_xlim(),*self.axis.get_ylim(),*box.bounds))+tuple(self.priority)
        if signature==self.signature:return
        self.signature=signature;used=[];changed=False
        primary=[i for i,n in enumerate(self.nodes) if n.get('kind')=='food' or any(h in n['name'] for h in HUBS)]
        order=list(dict.fromkeys(self.priority+primary+list(range(len(self.nodes)))))
        for a in self.annotations:a.set_visible(False)
        for i in order:
            n=self.nodes[i];a=self.annotations[i];px,py=self.axis.transData.transform((n['x'],n['y']))
            if not box.contains(px,py):continue
            if self.mode=='key' and i not in self.priority and i not in primary and len(used)>=14:continue
            for dx,dy,ha,va in ((6,5,'left','bottom'),(-6,5,'right','bottom'),(6,-5,'left','top'),(-6,-5,'right','top'),(0,12,'center','bottom'),(0,-12,'center','top')):
                a.set_position((dx,dy));a.set_ha(ha);a.set_va(va);a.set_visible(True);bounds=a.get_window_extent(event.renderer).expanded(1.035,1.12)
                if box.contains(bounds.x0,bounds.y0) and box.contains(bounds.x1,bounds.y1) and not any(bounds.overlaps(b) for b in used):used.append(bounds);changed=True;break
                a.set_visible(False)
        if changed:self.axis.figure.canvas.draw_idle()
