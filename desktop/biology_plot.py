"""Direct views of the biological fields; no image filtering or invented veins."""
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap
try:
    from .biology_data import geometry
except ImportError:
    from biology_data import geometry

class BiologyPlot:
    def __init__(self,figure):self.figure=figure;self.run=None
    def setup(self,run):
        self.run=run;self.figure.clear();self.figure.get_layout_engine().set(rect=(.02,.05,.93,.94),hspace=.1,wspace=.12);grid=self.figure.add_gridspec(3,2,height_ratios=[1.7,1.7,1],width_ratios=[1,1])
        self.arena=self.figure.add_subplot(grid[:2,:]);self.coverage=self.figure.add_subplot(grid[2,0]);self.pulse=self.figure.add_subplot(grid[2,1]);self.flow=self.pulse.twinx()
        h=run['history'];self.coverage.plot(h['time'],h['body_area']/run['mass'].sum()*100,color='#356b50',lw=1.3,label='Occupied area · w > 1')
        self.coverage.set(xlabel='Model time',ylabel='Arena occupied (%)',ylim=(0,105),xlim=(0,h['time'][-1]));self.coverage.spines[['top','right']].set_visible(False);self.coverage.grid(alpha=.16)
        self.cursor=self.coverage.axvline(0,color='#555',lw=.8,ls='--');self.coverage.tick_params(labelsize=8);self.coverage.xaxis.label.set_size(9);self.coverage.yaxis.label.set_size(9)
        self.coverage.set_title('Migration · accumulated body proxy',loc='left',fontsize=10)
        self.figure.text(.02,.008,'Fields and flow are recorded numerical states. Model time and length are uncalibrated. Vein width ∝ D¼; display cutoff is shown above.',fontsize=8,color='#536159')
    def display(self,index,mode='Body + veins',cutoff=1.,follow=False):
        r=self.run;f=r['fields'];xy=r['xy'];tri=r['triangles'];t=r['history']['time'][index];ax=self.arena;ax.clear();ax.set_facecolor('#11241f');self.figure.set_facecolor('#fbfcf9')
        if mode=='Calcium':
            ax.tripcolor(*xy.T,tri,f['c'][index],shading='gouraud',cmap='viridis',vmin=3.4,vmax=8.0)
        elif mode=='Advancing margin':
            ax.tripcolor(*xy.T,tri,f['v'][index],shading='gouraud',cmap='YlGn',vmin=0,vmax=6)
        else:
            # Flat triangle classification avoids drawing biomass beyond its occupied cells.
            body=f['w'][index]
            ax.tricontourf(*xy.T,tri,body,levels=[-1,.1,.9,1,max(1.1,float(body.max())+1)],colors=['#1d3027','#798b45','#657443','#344d32'])
        polygon,_=geometry(r['settings']['arena']);closed=np.vstack([polygon,polygon[0]]);ax.plot(*closed.T,color='#b9c4a3',lw=.7)
        e=r['edges'][:,:2].astype(int);d=f['d'][index];use=d>=cutoff
        if mode!='Advancing margin':
            colors='#f1dc93' if mode=='Body + veins' else '#fff5c3'
            ax.add_collection(LineCollection(xy[e[use]],colors=colors,linewidths=.5*(d[use]/1.)**.25,zorder=4))
        seed=xy[r['inoculum']];ax.scatter(*seed.mean(axis=0),s=35,facecolors='none',edgecolors='#f4e7aa',lw=1,zorder=5)
        if index==0:ax.annotate('Inoculum',seed.mean(axis=0),xytext=(-65,18),textcoords='offset points',color='#fff3cd',fontsize=9,arrowprops=dict(arrowstyle='-',color='#fff3cd'))
        ax.set_aspect('equal');ax.set(xlim=(-.7,40.7),ylim=(-.7,max(polygon[:,1])+1.2));ax.set_xlabel('Length (model units)',fontsize=9);ax.set_ylabel('Length (model units)',fontsize=9);ax.tick_params(labelsize=8)
        ax.set_title(f'{mode}  ·  t = {t:g}  ·  shown veins D ≥ {cutoff:g}',loc='left',fontsize=11,pad=12)
        legend='Uncolonised arena · Advancing band · Accumulated body\nFine gold: conductivity D · Ring: inoculum' if mode=='Body + veins' else 'Calcium c: fixed colour scale 3.4–8.0' if mode=='Calcium' else 'Activator v: fixed colour scale 0–6'
        ax.text(.012,.025,legend,transform=ax.transAxes,fontsize=7.5,color='#d9e3cd',bbox=dict(facecolor='#11241f',edgecolor='none',alpha=.9),zorder=8)
        if follow:
            occupied=(f['w'][index]>=.1)|r['inoculum'];p0=xy[occupied].min(axis=0);p1=xy[occupied].max(axis=0);centre=.5*(p0+p1);height=max(8.,p1[1]-p0[1]+3);width=max(14.,p1[0]-p0[0]+4,height*2.3);ax.set_xlim(centre[0]-width/2,centre[0]+width/2);ax.set_ylim(centre[1]-height/2,centre[1]+height/2)
        self.cursor.set_xdata([t,t]);self.pulse.clear();self.flow.clear();p=r['probe'];end=max(8.,t);start=max(0.,end-8.);select=(p['time']>=start)&(p['time']<=end)
        self.pulse.plot(p['time'][select],p['c'][select],color='#426b9b',lw=1,label='Calcium at inoculum');self.flow.plot(p['time'][select],p['q' if 'q' in p.dtype.names else 'q0'][select],color='#b47c35',lw=.85,alpha=.85,label='Signed flow on edge 0')
        self.flow.axhline(0,color='#b47c35',lw=.4,alpha=.5);self.pulse.set(xlim=(start,end),xlabel='Model time · 8-unit probe window',ylabel='Calcium c');self.flow.set_ylabel(f"Signed q · edge {r['engine'].get('probe_edge',0)}",fontsize=8,color='#9e6e30');self.flow.yaxis.set_label_position('right');self.flow.yaxis.tick_right();self.pulse.tick_params(labelsize=8);self.flow.tick_params(labelsize=8);self.pulse.yaxis.label.set_size(9);self.pulse.xaxis.label.set_size(9);self.pulse.spines['top'].set_visible(False);self.flow.spines['top'].set_visible(False);self.pulse.grid(alpha=.15)
        self.pulse.set_title('Calcium and flow · sampled every integration step',loc='left',fontsize=10)
        return dict(area=float(r['history']['body_area'][index]),total=float(r['mass'].sum()),veins=int(use.sum()),max_d=float(d.max()),time=float(t))
