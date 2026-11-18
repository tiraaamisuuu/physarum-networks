"""Geographic food/restriction design canvas; never alters a recorded run."""
import numpy as np
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle
from matplotlib.widgets import RectangleSelector
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QCheckBox,QPushButton
try:
    from .spatial_data import within_coverage
except ImportError:
    from spatial_data import within_coverage


class LayoutCanvas(FigureCanvasQTAgg):
    station_clicked=Signal(str)
    restriction_drawn=Signal(object)
    def __init__(self):
        self.figure=Figure(figsize=(11,7),dpi=100,layout='compressed',facecolor='white');super().__init__(self.figure)
        self.axis=None;self.scene=None;self.selector=None;self.drawing=False;self.names=False;self.elevation=False
        self.mpl_connect('button_press_event',self.click);self.mpl_connect('motion_notify_event',self.hover)
    def setup(self,scene,reset=False):
        limits=(self.axis.get_xlim(),self.axis.get_ylim()) if self.axis is not None and not reset else None
        if self.selector:self.selector.disconnect_events()
        self.scene=scene;self.figure.clear();self.axis=self.figure.add_subplot();axis=self.axis;axis.set_facecolor('#fafbf8')
        catalog=scene['geography']['station_catalog'];self.catalog=[n for n in catalog if within_coverage(n,scene['geography'])]
        self.xy=np.array([[n['x'],n['y']] for n in self.catalog]);selected={n['key'] for n in scene['nodes'] if n['kind']=='station'}
        self.selected=np.array([n['tfl_id'] in selected for n in self.catalog])
        if self.elevation:
            elevation=scene['geography']['elevation'];image=axis.pcolormesh(elevation['x'],elevation['y'],elevation['metres'],shading='auto',cmap='gist_earth',alpha=.28,zorder=0)
            bar=self.figure.colorbar(image,ax=axis,fraction=.03,pad=.015);bar.set_label('Surface elevation (metres) · context only',fontsize=8);bar.ax.tick_params(labelsize=8)
        axis.add_collection(LineCollection([way['xy_km'] for way in scene['geography']['river']],colors='#83b3c4',linewidths=1.7,zorder=1))
        axis.scatter(*self.xy[~self.selected].T,s=18,facecolors='#e5e9e1',edgecolors='#8e9b91',linewidths=.6,zorder=3,label='Available station')
        axis.scatter(*self.xy[self.selected].T,s=38,facecolors='#e5b663',edgecolors='#936c29',linewidths=.9,zorder=4,label='Selected food source')
        for x0,y0,x1,y1 in scene['barriers']:axis.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor='#c89686',edgecolor='#a76351',hatch='//',alpha=.35,zorder=2))
        if self.names:
            for n,use in zip(self.catalog,self.selected):
                if use:axis.annotate(n['name'],(n['x'],n['y']),xytext=(4,4),textcoords='offset points',fontsize=7,zorder=5)
        axis.set_aspect('equal');axis.set_xlabel('British National Grid easting (km)',fontsize=9);axis.set_ylabel('Northing (km)',fontsize=9);axis.tick_params(labelsize=8);axis.spines[['top','right']].set_visible(False)
        if limits:axis.set_xlim(*limits[0]);axis.set_ylim(*limits[1])
        else:axis.set_xlim(self.xy[:,0].min()-.3,self.xy[:,0].max()+.3);axis.set_ylim(self.xy[:,1].min()-.3,self.xy[:,1].max()+.3)
        axis.set_title(f"Experiment design · {self.selected.sum()} food sources · {len(scene['barriers'])} restricted areas",loc='left',fontsize=12,pad=16)
        axis.legend(loc='upper right',frameon=True,fontsize=8)
        credit='TfL coordinates · © OpenStreetMap contributors'
        if self.elevation:credit+='\nSurface elevation: Copernicus DEM / Open-Meteo (CC BY 4.0); not underground geology'
        axis.text(.01,.01,credit,transform=axis.transAxes,fontsize=7,color='#40514b',bbox={'facecolor':'white','alpha':.85,'edgecolor':'none'},zorder=8)
        self.annotation=axis.annotate('',xy=(0,0),xytext=(8,10),textcoords='offset points',fontsize=9,bbox={'facecolor':'white','edgecolor':'#b8c4b8','alpha':.95},zorder=10,visible=False)
        self.selector=RectangleSelector(axis,self.rectangle,useblit=False,button=[1],minspanx=.05,minspany=.05,spancoords='data',interactive=False);self.selector.set_active(self.drawing);self.draw_idle()
    def nearest(self,event):
        if event.inaxes!=self.axis or self.scene is None:return None
        pixels=self.axis.transData.transform(self.xy);dist=np.linalg.norm(pixels-np.array([event.x,event.y]),axis=1);i=int(dist.argmin())
        return i if dist[i]<=11 else None
    def click(self,event):
        if self.drawing or event.button!=1 or (self.toolbar and self.toolbar.mode):return
        i=self.nearest(event)
        if i is not None:self.station_clicked.emit(self.catalog[i]['tfl_id'])
    def hover(self,event):
        if self.scene is None or self.drawing:return
        i=self.nearest(event)
        if i is None:
            if self.annotation.get_visible():self.annotation.set_visible(False);self.draw_idle()
            return
        self.annotation.xy=self.xy[i];self.annotation.set_text(self.catalog[i]['name']+('\nSelected food · click to remove' if self.selected[i] else '\nClick to add as food'));self.annotation.set_visible(True);self.draw_idle()
    def rectangle(self,start,end):
        if not self.drawing or any(v is None for v in (start.xdata,start.ydata,end.xdata,end.ydata)):return
        self.restriction_drawn.emit([min(start.xdata,end.xdata),min(start.ydata,end.ydata),max(start.xdata,end.xdata),max(start.ydata,end.ydata)])
    def set_drawing(self,value):
        self.drawing=value
        if self.selector:self.selector.set_active(value)


class LayoutPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;layout=QVBoxLayout(self)
        instruction=QLabel('DESIGN VIEW · Click a station to add/remove food. Hover for its name. Draw exclusions to restrict candidate routes before computing. This map shows your design; the Network tab retains the saved run until you compute again.');instruction.setWordWrap(True);layout.addWidget(instruction)
        bar=QHBoxLayout();names=QCheckBox('Selected station names');terrain=QCheckBox('Surface elevation');bar.addWidget(names);bar.addWidget(terrain)
        self.draw_button=QPushButton('Draw restricted area');self.draw_button.setCheckable(True);bar.addWidget(self.draw_button)
        remove=QPushButton('Remove last restriction');remove.clicked.connect(owner.remove_restriction);bar.addWidget(remove);reset=QPushButton('Reset map view');bar.addWidget(reset);bar.addStretch();layout.addLayout(bar)
        self.canvas=LayoutCanvas();layout.addWidget(NavigationToolbar2QT(self.canvas,self));layout.addWidget(self.canvas,1)
        self.canvas.station_clicked.connect(owner.toggle_station);self.canvas.restriction_drawn.connect(owner.add_restriction);self.draw_button.toggled.connect(self.canvas.set_drawing)
        names.toggled.connect(lambda value:self.overlay('names',value));terrain.toggled.connect(lambda value:self.overlay('elevation',value));reset.clicked.connect(lambda:self.canvas.setup(owner.scene,True))
    def overlay(self,key,value):setattr(self.canvas,key,value);self.canvas.setup(self.owner.scene)
    def refresh(self):self.canvas.setup(self.owner.scene)
