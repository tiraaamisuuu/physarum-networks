"""Native laboratory for the paper's pressure-flow and tube-adaptation equations."""
import copy
import csv
import json
from pathlib import Path
import threading
import time
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.widgets import RectangleSelector
from PySide6.QtCore import Qt,QThread,QTimer,Signal,QUrl
from PySide6.QtGui import QDesktopServices,QPalette,QColor
from PySide6.QtWidgets import (QMainWindow,QWidget,QSplitter,QVBoxLayout,QHBoxLayout,QFormLayout,QGroupBox,
    QLabel,QPushButton,QDoubleSpinBox,QSpinBox,QComboBox,QCheckBox,QSlider,QTabWidget,QTableWidget,
    QTableWidgetItem,QHeaderView,QFileDialog,QMessageBox,QScrollArea,QDialog,QTextBrowser)
try:
    from .mesh_data import ROOT,DEFAULT_MESH,DEFAULT_CUTOFF,default_scene,load_mesh_run,run_mesh_experiment,mesh_metrics,effective_mesh_settings,compare_mesh_trajectories,solver_extrema
    from .mesh_plot import draw_tubes,tube_widths,export_snapshot
    from .spatial_viewer import StationDialog
    from .mesh_sweep_view import SweepPanel
    from .mesh_layout import LayoutPanel
except ImportError:
    from mesh_data import ROOT,DEFAULT_MESH,DEFAULT_CUTOFF,default_scene,load_mesh_run,run_mesh_experiment,mesh_metrics,effective_mesh_settings,compare_mesh_trajectories,solver_extrema
    from mesh_plot import draw_tubes,tube_widths,export_snapshot
    from spatial_viewer import StationDialog
    from mesh_sweep_view import SweepPanel
    from mesh_layout import LayoutPanel


class MeshWorker(QThread):
    completed=Signal(object)
    failed=Signal(str)
    def __init__(self,scene,settings,parent=None):
        super().__init__(parent);self.scene=copy.deepcopy(scene);self.settings=copy.deepcopy(settings);self.cancel=threading.Event()
    def run(self):
        try:self.completed.emit(run_mesh_experiment(self.scene,self.settings,cancel=self.cancel))
        except Exception as error:self.failed.emit(str(error))


class TubeCanvas(FigureCanvasQTAgg):
    picked=Signal(str,int)
    restricted=Signal(object)
    def __init__(self):
        self.figure=Figure(figsize=(12,7),dpi=100,layout='constrained',facecolor='white')
        super().__init__(self.figure);self.setMinimumSize(640,430);self.run=None;self.index=0;self.selected=0
        self.names=False;self.background=False;self.cutoff=DEFAULT_CUTOFF
        self.edit_restriction=False;self.rectangle_selector=None;self.terrain=False;self.draft_patches=[]
        self.mpl_connect('button_press_event',self.pick)
        self.figure.text(.5,.5,'Prepare a tube-network experiment',ha='center',color='#59665e')
    def setup(self,run,cutoff,names=False,background=False):
        if self.rectangle_selector:self.rectangle_selector.disconnect_events()
        self.run=run;self.cutoff=cutoff;self.names=names;self.background=background;self.selected=min(self.selected,len(run.mesh['edges'])-1)
        self.figure.clear();grid=self.figure.add_gridspec(3,4,width_ratios=[1,1,1,1.2])
        self.map=self.figure.add_subplot(grid[:,:3]);self.dp=self.figure.add_subplot(grid[0,3]);self.qp=self.figure.add_subplot(grid[1,3]);self.cp=self.figure.add_subplot(grid[2,3])
        self.links=draw_tubes(self.map,run,self.index,cutoff,names,background)
        # Replace these dynamic artists at each frame; static river, food coordinates and labels stay fixed.
        self.terminals=self.map.collections[-1]
        if self.terrain:
            elevation=run.scene['geography']['elevation']
            terrain=self.map.pcolormesh(elevation['x'],elevation['y'],elevation['metres'],shading='auto',cmap='gist_earth',alpha=.23,zorder=0)
            colorbar=self.figure.colorbar(terrain,ax=self.map,fraction=.025,pad=.015);colorbar.set_label('Surface elevation m · context only',fontsize=7);colorbar.ax.tick_params(labelsize=7)
        self.rectangle_selector=RectangleSelector(self.map,self.rectangle,useblit=False,button=[1],minspanx=.05,minspany=.05,spancoords='data',interactive=False)
        self.rectangle_selector.set_active(self.edit_restriction);self.draft_patches=[]
        self.highlight=self.map.plot([],[],color='#c36e2d',lw=2,zorder=8)[0]
        self.title=self.map.set_title('London · exact food coordinates',loc='left',fontsize=11,pad=14)
        self.xy=np.array([[n['x'],n['y']] for n in run.mesh['nodes']]);self.endpoints=np.array([[e['from'],e['to']] for e in run.mesh['edges']])
        self.edge_d=self.dp.plot([],[],color='#263d38',lw=1.2)[0];self.edge_q=self.qp.plot([],[],color='#196fad',lw=.8)[0]
        self.d_cursor=self.dp.axvline(0,color='#a5784d',lw=.8,ls='--');self.q_cursor=self.qp.axvline(0,color='#a5784d',lw=.8,ls='--')
        for axis,label in ((self.dp,'Selected tube · conductivity D'),(self.qp,'Selected tube · signed flow Q'),(self.cp,'Foods in largest component')):
            axis.set_title(label,loc='left',fontsize=8,pad=10);axis.tick_params(labelsize=7);axis.spines[['top','right']].set_visible(False);axis.grid(alpha=.12,lw=.5)
        sample=np.unique(np.linspace(0,len(run.times)-1,min(41,len(run.times))).astype(int))
        self.history=[mesh_metrics(run,int(i),cutoff) for i in sample]
        self.cp.plot(run.times[sample],[m['largest_food_component'] for m in self.history],color='#13856e',lw=1.2)
        self.cp.axhline(run.food_count,color='#bbb',lw=.6,ls=':');self.cp.set_ylim(0,run.food_count+2)
        self.length_axis=self.cp.twinx();self.length_axis.plot(run.times[sample],[m['length_km'] if m['length_km']>0 else np.nan for m in self.history],color='#b07a3b',lw=1.,ls='--')
        self.length_axis.set_yscale('log');self.length_axis.set_ylabel('Retained km · log scale',fontsize=7,color='#95652e');self.length_axis.tick_params(labelsize=6,colors='#95652e');self.length_axis.spines[['top']].set_visible(False)
        self.cp.set_title('Largest food component · dashed: retained km',loc='left',fontsize=7.5,pad=10)
        self.c_cursor=self.cp.axvline(0,color='#a5784d',lw=.8,ls='--');self.cp.set_xlabel('Model time · arbitrary units',fontsize=7)
        self.figure.text(.01,.005,f'TfL coordinates · © OpenStreetMap contributors   |   D ≥ {cutoff:g}   |   width ∝ D¼; 1.2 pt at D = 0.5   |   blue / orange = source / sink',fontsize=7,color='#59665e')
        if self.terrain:self.map.text(.01,.01,'Surface elevation: Copernicus DEM / Open-Meteo (CC BY 4.0)\nContext only; not underground geology',transform=self.map.transAxes,fontsize=6.5,color='#40514b',bbox={'facecolor':'white','alpha':.85,'edgecolor':'none'},zorder=10)
        self.select_edge(self.selected);self.set_frame(self.index)
    def select_edge(self,k):
        self.selected=k
        if self.run is None:return
        for axis,line,values in ((self.dp,self.edge_d,self.run.d),(self.qp,self.edge_q,self.run.q)):
            line.set_data(self.run.times,values[:,k]);axis.relim();axis.autoscale_view();axis.set_xlim(0,self.run.times[-1])
        self.set_frame(self.index)
    def set_frame(self,index):
        self.index=index
        if self.run is None:return
        run=self.run;keep=run.d[index]>=self.cutoff
        self.links.set_segments(self.xy[self.endpoints[keep]]);self.links.set_linewidths(tube_widths(run.d[index,keep]))
        self.terminals.set_offsets(self.xy[run.pairs[index]])
        self.highlight.set_data(*self.xy[self.endpoints[self.selected]].T)
        self.highlight.set_visible(run.d[index,self.selected]>=self.cutoff)
        self.title.set_text(f'London · t = {run.times[index]:.3g} · {int(keep.sum())} retained tube segments')
        for cursor in (self.d_cursor,self.q_cursor,self.c_cursor):cursor.set_xdata([run.times[index]]*2)
        self.draw_idle()
    def pick(self,event):
        if self.edit_restriction or self.run is None or event.inaxes!=self.map or event.button!=1:return
        if self.toolbar and self.toolbar.mode:return
        xy=self.map.transData.transform(self.xy);mouse=np.array([event.x,event.y]);dist=np.linalg.norm(xy[:self.run.food_count]-mouse,axis=1)
        food=int(dist.argmin())
        if dist[food]<10:self.picked.emit('food',food);return
        a,b=xy[self.endpoints[:,0]],xy[self.endpoints[:,1]];ab=b-a
        t=np.clip(np.sum((mouse-a)*ab,axis=1)/np.sum(ab*ab,axis=1),0,1);distance=np.linalg.norm(a+t[:,None]*ab-mouse,axis=1)
        distance[self.run.d[self.index]<self.cutoff]=np.inf;k=int(distance.argmin())
        if distance[k]<8:self.select_edge(k);self.picked.emit('edge',k)
    def rectangle(self,start,end):
        if not self.edit_restriction or any(v is None for v in (start.xdata,start.ydata,end.xdata,end.ydata)):return
        self.restricted.emit([min(start.xdata,end.xdata),min(start.ydata,end.ydata),max(start.xdata,end.xdata),max(start.ydata,end.ydata)])
    def show_draft_restrictions(self,scene):
        for patch in self.draft_patches:patch.remove()
        self.draft_patches=[]
        if self.run is None:return
        if scene['barriers']!=self.run.scene['barriers']:
            for x0,y0,x1,y1 in scene['barriers']:
                patch=Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor='#b64b38',linewidth=1.2,ls='--',zorder=9);self.map.add_patch(patch);self.draft_patches.append(patch)
        self.draw_idle()


class MeshViewer(QMainWindow):
    def __init__(self,auto_run=True):
        super().__init__();self.scene=default_scene();self.run_data=None;self.worker=None;self.index=0;self.playing=False;self.playhead=0.;self.closing=False;self.previous=None;self.children_windows=[];self.selected_pick=('edge',0)
        palette=QPalette()
        for role,color in ((QPalette.ColorRole.Window,'#f6f7f3'),(QPalette.ColorRole.WindowText,'#263d38'),(QPalette.ColorRole.Base,'#ffffff'),(QPalette.ColorRole.AlternateBase,'#f1f4ee'),(QPalette.ColorRole.Text,'#263d38'),(QPalette.ColorRole.Button,'#eef1eb'),(QPalette.ColorRole.ButtonText,'#263d38'),(QPalette.ColorRole.Highlight,'#287c66'),(QPalette.ColorRole.HighlightedText,'#ffffff')):palette.setColor(role,QColor(color))
        self.setPalette(palette);self.setAutoFillBackground(True)
        self.setWindowTitle('Physarum — Tube-network laboratory');self.resize(1440,930);self.setMinimumSize(1100,760)
        self.controls={};self.build_ui();self.refresh_pairs();self.set_settings(DEFAULT_MESH)
        self.timer=QTimer(self);self.timer.setInterval(50);self.timer.timeout.connect(self.tick);self.timer.start();self.last_tick=time.monotonic()
        if auto_run:QTimer.singleShot(0,self.compute)
    def build_ui(self):
        menu=self.menuBar().addMenu('&File')
        menu.addAction('Open recorded tube run…').triggered.connect(self.open_run)
        menu.addAction('Save experiment design…').triggered.connect(self.save_design)
        menu.addAction('Open experiment design…').triggered.connect(self.open_design)
        menu.addAction('Import demand weights CSV…').triggered.connect(self.import_demand)
        menu.addAction('Save demand CSV template…').triggered.connect(self.demand_template)
        menu.addAction('Export current snapshot…').triggered.connect(self.export)
        menu.addAction('Open run files').triggered.connect(self.open_files)
        menu.addSeparator();menu.addAction('Close').triggered.connect(self.close)
        other=self.menuBar().addMenu('Other models')
        other.addAction('Four-node mathematical fixture').triggered.connect(lambda:self.open_other('fixture'))
        other.addAction('Particle foraging · experimental').triggered.connect(lambda:self.open_other('particles'))
        split=QSplitter(Qt.Orientation.Horizontal);self.setCentralWidget(split)
        sidebar=QWidget();sidebar.setMinimumWidth(290);sidebar.setMaximumWidth(390);sidebar_layout=QVBoxLayout(sidebar);sidebar_layout.setContentsMargins(0,0,0,0)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);sidebar_layout.addWidget(scroll,1)
        side=QWidget();layout=QVBoxLayout(side);layout.setContentsMargins(18,18,18,18);layout.setSpacing(12);scroll.setWidget(side);split.addWidget(sidebar)
        fixed=QWidget();self.fixed_controls=QVBoxLayout(fixed);self.fixed_controls.setContentsMargins(18,8,18,12);sidebar_layout.addWidget(fixed)
        heading=QLabel('TUBE NETWORK\nLABORATORY');heading.setStyleSheet('font-size:20px; font-weight:600; color:#263d38;');layout.addWidget(heading)
        intro=QLabel('Pressure drives flow. Flow reinforces tubes.\nUnused tubes decay.');intro.setWordWrap(True);layout.addWidget(intro)
        choose=QPushButton('Choose station food sources…');choose.clicked.connect(self.choose_foods);layout.addWidget(choose);self.food_label=QLabel();layout.addWidget(self.food_label)
        restriction_group=QGroupBox('Geographic restrictions');rl=QVBoxLayout(restriction_group)
        self.restriction_button=QPushButton('Draw a restricted area');self.restriction_button.setCheckable(True);self.restriction_button.toggled.connect(self.restriction_mode);rl.addWidget(self.restriction_button)
        undo=QPushButton('Remove last restriction');undo.clicked.connect(self.remove_restriction);rl.addWidget(undo)
        self.restriction_label=QLabel('0 restricted areas');rl.addWidget(self.restriction_label);layout.addWidget(restriction_group)
        presets=QComboBox();presets.addItems(['Choose a starting experiment…','Explore lower flow (I₀ = 0.2)','Explore more alternatives (γ = 1.15)','Default tube parameters']);presets.setToolTip('These are parameter starting points. Their effect depends on the food layout, mesh, seed and integration settings.');presets.currentIndexChanged.connect(lambda index:self.apply_preset(index,presets));layout.addWidget(presets)
        group=QGroupBox('Model parameters');form=QFormLayout(group)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.integrator=QComboBox();self.integrator.addItem('Euler · first order','euler');self.integrator.addItem('Heun · second order','heun');form.addRow('Integration',self.integrator);self.integrator.setToolTip('Heun solves pressures at both stages. Compare dt refinements under the same held forcing; a higher formal order is not an accuracy guarantee for every experiment.');self.integrator.currentIndexChanged.connect(self.draft)
        definitions=[('current','Injected flow I₀',.1,5,.1,2),('gamma','Response γ',.5,3,.05,2),('duration','Model duration',1,40,5,2),('dt','Time step Δt',.005,.25,.00625,5),('switch_interval','Switch demand every',.01,2,.05,5),('spacing','Mesh spacing (km)',.25,1.5,.05,2),('river_penalty','River crossing cost (km)',0,10,.5,2),('initial_conductivity','Initial conductivity D',.01,1,.05,2),('initial_noise','Initial variation ±',0,.5,.05,2)]
        tips={'gamma':'Controls the nonlinear reinforcement curve, not simply tube thinness.','dt':'Refine dt while holding the demand switching interval fixed. Duration and switching interval must be multiples of dt.','spacing':'Controls candidate routes. Compare mesh resolutions and random seeds before interpreting geometry.','river_penalty':'Assumed additional effective resistance length per crossing. This is not a measured engineering cost. Zero leaves the Thames as context only.','initial_noise':'Uniform seeded variation relative to the initial conductivity.'}
        for key,label,low,high,step,decimals in definitions:
            box=QDoubleSpinBox();box.setRange(low,high);box.setSingleStep(step);box.setDecimals(decimals);box.setKeyboardTracking(False);box.setToolTip(tips.get(key,''));form.addRow(label,box);self.controls[key]=box;box.valueChanged.connect(self.draft)
        seed=QSpinBox();seed.setRange(0,2**31-1);seed.setKeyboardTracking(False);form.addRow('Random seed',seed);self.controls['seed']=seed;seed.valueChanged.connect(self.draft);layout.addWidget(group)
        demand=QGroupBox('Food-to-food forcing');df=QFormLayout(demand);self.mode=QComboBox();self.mode.addItem('Random food pair','random_pairs');self.mode.addItem('Fixed source / sink','fixed_pair');self.mode.addItem('Weighted pairs from CSV','weighted_pairs');df.addRow(self.mode)
        self.source=QComboBox();self.sink=QComboBox();df.addRow('Source',self.source);df.addRow('Sink',self.sink);layout.addWidget(demand)
        for box in (self.source,self.sink):box.setMinimumContentsLength(12);box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        import_weights=QPushButton('Import pair weights…');import_weights.clicked.connect(self.import_demand);df.addRow(import_weights)
        self.demand_label=QLabel('Uniform sampling of selected food pairs.');self.demand_label.setWordWrap(True);df.addRow(self.demand_label)
        for box in (self.mode,self.source,self.sink):box.currentIndexChanged.connect(self.draft)
        self.compute_button=QPushButton('Compute tube experiment');self.compute_button.setMinimumHeight(36);self.compute_button.setStyleSheet('QPushButton { background:#263d38; color:white; padding:7px; border-radius:3px; }');self.compute_button.clicked.connect(self.compute);self.fixed_controls.addWidget(self.compute_button)
        self.cancel_button=QPushButton('Cancel computation');self.cancel_button.clicked.connect(self.cancel);self.cancel_button.setVisible(False);self.fixed_controls.addWidget(self.cancel_button)
        reset=QPushButton('Restore London defaults');reset.clicked.connect(self.reset);self.fixed_controls.addWidget(reset)
        note=QLabel('This is the paper’s numerical approach: a pre-existing fine mesh adapts into tubes. It does not simulate the biological expanding margin.\n\nTime and flow are model units. Station coordinates are real; network geometry and crossing costs are experimental.');note.setWordWrap(True);note.setStyleSheet('color:#59665e; font-size:11px;');layout.addWidget(note);layout.addStretch()
        right=QWidget();main=QVBoxLayout(right);main.setContentsMargins(16,16,16,12);split.addWidget(right);split.setSizes([330,1210])
        self.banner=QLabel('Preparing the experiment…');self.banner.setWordWrap(True);self.banner.setStyleSheet('padding:9px; background:#eef2ed; color:#263d38;');main.addWidget(self.banner)
        self.narrative=QLabel('');self.narrative.setWordWrap(True);main.addWidget(self.narrative)
        self.tabs=QTabWidget();main.addWidget(self.tabs,1)
        workspace=QWidget();wl=QVBoxLayout(workspace);wl.setContentsMargins(0,4,0,0)
        display=QHBoxLayout();display.addWidget(QLabel('Retain D ≥'));self.cutoff=QComboBox()
        for x in (1e-6,1e-5,1e-4,1e-3,1e-2):self.cutoff.addItem(f'{x:g}',x)
        self.cutoff.setCurrentIndex(2);self.cutoff.currentIndexChanged.connect(self.replot);display.addWidget(self.cutoff)
        self.names=QCheckBox('Food names');self.background=QCheckBox('Candidate mesh');self.terrain=QCheckBox('Surface elevation');display.addWidget(self.names);display.addWidget(self.background);display.addWidget(self.terrain);self.names.toggled.connect(self.replot);self.background.toggled.connect(self.replot);self.terrain.toggled.connect(self.replot);display.addStretch()
        export=QPushButton('Export figure + data…');export.clicked.connect(self.export);display.addWidget(export);wl.addLayout(display)
        self.canvas=TubeCanvas();self.toolbar=NavigationToolbar2QT(self.canvas,self);wl.addWidget(self.toolbar);wl.addWidget(self.canvas,1);self.canvas.picked.connect(self.picked)
        self.canvas.restricted.connect(self.add_restriction)
        self.tabs.addTab(workspace,'Network')
        self.layout_panel=LayoutPanel(self);self.tabs.addTab(self.layout_panel,'Layout')
        self.food_table=QTableWidget(0,6);self.food_table.setHorizontalHeaderLabels(['Food source','Foods in component','Incident tubes','Maximum incident D','Model pressure','Exact vertex'])
        self.food_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.food_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.tabs.addTab(self.food_table,'Food sources')
        self.record=QTextBrowser();self.record.setOpenExternalLinks(True);self.tabs.addTab(self.record,'Equations & record')
        self.comparison=QTextBrowser();self.comparison.setText('After a second experiment, this tab compares the previous and current final states at the same cutoff.');self.tabs.addTab(self.comparison,'Compare runs')
        self.sweep_panel=SweepPanel(self);self.tabs.addTab(self.sweep_panel,'Parameter study')
        self.measurements=QLabel('');self.measurements.setWordWrap(True);self.measurements.setStyleSheet('padding:8px; background:#f4f5f1; color:#263d38;');main.addWidget(self.measurements)
        bar=QHBoxLayout();self.play=QPushButton('Play adaptation');self.play.clicked.connect(self.toggle);bar.addWidget(self.play)
        for text,callback in [('Restart',lambda:self.display(0)),('Final state',self.final_state),('Analyze snapshot',self.analyze)]:
            button=QPushButton(text);button.clicked.connect(callback);bar.addWidget(button)
        bar.addStretch();bar.addWidget(QLabel('Playback'));self.speed=QComboBox()
        for value in (.5,1.,2.,5.):self.speed.addItem(f'{value:g} model units / s',value)
        self.speed.setCurrentIndex(1);bar.addWidget(self.speed);main.addLayout(bar)
        self.slider=QSlider(Qt.Orientation.Horizontal);self.slider.valueChanged.connect(self.display);main.addWidget(self.slider)
        self.state_label=QLabel('');main.addWidget(self.state_label);self.selection=QLabel('Click a tube to inspect D and Q, or a food source for its exact vertex.');self.selection.setWordWrap(True);main.addWidget(self.selection)
    def settings(self):
        return {**{k:box.value() for k,box in self.controls.items()},'demand_mode':self.mode.currentData(),'source_id':self.source.currentData(),'sink_id':self.sink.currentData(),'integrator':self.integrator.currentData()}
    def set_settings(self,settings):
        for k,box in self.controls.items():box.setValue(settings[k])
        self.integrator.setCurrentIndex(self.integrator.findData(settings.get('integrator','euler')))
        self.mode.setCurrentIndex(self.mode.findData(settings['demand_mode']))
        for box,key in ((self.source,'source_id'),(self.sink,'sink_id')):
            ix=box.findData(settings[key]);box.setCurrentIndex(max(0,ix))
        self.draft()
    def refresh_pairs(self):
        for box in (self.source,self.sink):
            key=box.currentData();box.clear()
            for n in self.scene['nodes']:
                if n['kind']=='station':box.addItem(n['name'],n['key'])
            box.setCurrentIndex(max(0,box.findData(key)))
        self.food_label.setText(f"{sum(n['kind']=='station' for n in self.scene['nodes'])} real food-source vertices")
    def draft(self,*_):
        self.restriction_label.setText(f"{len(self.scene['barriers'])} restricted areas · compute to apply")
        self.canvas.show_draft_restrictions(self.scene)
        self.layout_panel.refresh()
        fixed=self.mode.currentData()=='fixed_pair';self.source.setEnabled(fixed);self.sink.setEnabled(fixed)
        count=len(self.scene.get('weighted_demand',{}).get('pairs',[]))
        self.demand_label.setText(f'{count} imported weighted pairs · weights control sampling frequency, not I₀.' if self.mode.currentData()=='weighted_pairs' else 'Uniform sampling of selected food pairs.' if not fixed else 'One fixed food pair carries I₀ throughout the experiment.')
        if self.worker and self.worker.isRunning():return
        changed=self.run_data is None or effective_mesh_settings(self.settings())!=effective_mesh_settings(self.run_data.settings) or self.scene!=self.run_data.scene
        self.banner.setText('DESIGN CHANGED · Compute to apply these controls. The figure still shows the recorded run.' if changed and self.run_data else 'Ready to compute a fine-mesh tube experiment.' if changed else f"RECORDED TUBE RUN · γ {self.run_data.settings['gamma']:g} · I₀ {self.run_data.settings['current']:g} · {self.run_data.settings.get('integrator','euler')} · seed {self.run_data.settings['seed']} · {self.run_data.food_count} foods")
    def choose_foods(self):
        dialog=StationDialog(self.scene['geography'],{n['tfl_id'] for n in self.scene['nodes'] if n['kind']=='station'},self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        keys=dialog.selected()
        if not 3<=len(keys)<=80:QMessageBox.warning(self,'Food count','Choose 3–80 food sources.');return
        lookup={n['tfl_id']:n for n in self.scene['geography']['station_catalog']};nodes=[]
        for key in keys:node=copy.deepcopy(lookup[key]);node['key']=key;nodes.append(node)
        self.scene={**self.scene,'nodes':nodes};self.refresh_pairs();self.draft()
    def reset(self):self.scene=default_scene();self.refresh_pairs();self.set_settings(DEFAULT_MESH)
    def apply_preset(self,index,box):
        if index==1:self.controls['current'].setValue(.2)
        elif index==2:self.controls['gamma'].setValue(1.15)
        elif index==3:self.set_settings(DEFAULT_MESH)
        box.setCurrentIndex(0)
    def toggle_station(self,key):
        foods=[n for n in self.scene['nodes'] if n['kind']=='station'];keys={n['key'] for n in foods}
        if key in keys:
            if len(foods)<=3:QMessageBox.warning(self,'Food count','Keep at least three food sources.');return
            self.scene['nodes']=[n for n in self.scene['nodes'] if n['key']!=key]
        else:
            if len(foods)>=80:QMessageBox.warning(self,'Food count','Use at most 80 food sources per experiment.');return
            node=copy.deepcopy(next(n for n in self.scene['geography']['station_catalog'] if n['tfl_id']==key));node['key']=key
            if any(x0<=node['x']<=x1 and y0<=node['y']<=y1 for x0,y0,x1,y1 in self.scene['barriers']):QMessageBox.warning(self,'Restricted station','Remove the restriction before placing food inside it.');return
            self.scene['nodes']=[*self.scene['nodes'],node]
        self.refresh_pairs();self.draft()
    def restriction_mode(self,enabled):
        self.canvas.edit_restriction=enabled
        if self.canvas.rectangle_selector:self.canvas.rectangle_selector.set_active(enabled)
        self.restriction_button.setText('Drag a rectangle on the map' if enabled else 'Draw a restricted area')
        self.layout_panel.draw_button.setChecked(enabled)
        if enabled:self.pause();self.tabs.setCurrentWidget(self.layout_panel)
    def add_restriction(self,rect):
        if any(r[0]<=n['x']<=r[2] and r[1]<=n['y']<=r[3] for r in [rect] for n in self.scene['nodes'] if n['kind']=='station'):
            QMessageBox.warning(self,'Food inside restriction','The rectangle contains a food source. Move its boundary or remove that food source first.');return
        self.scene['barriers'].append(rect);self.restriction_button.setChecked(False);self.layout_panel.draw_button.setChecked(False);self.draft()
    def remove_restriction(self):
        if self.scene['barriers']:self.scene['barriers'].pop();self.draft()
    def compute(self):
        if (self.worker and self.worker.isRunning()) or self.sweep_panel.running():return
        self.pause();self.worker=MeshWorker(self.scene,self.settings(),self);self.worker.completed.connect(self.accept_run);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.worker_done)
        self.compute_button.setEnabled(False);self.cancel_button.setVisible(True);self.banner.setText('COMPUTING · steady pressure solves and simultaneous tube adaptation. Full states are saved automatically.');self.worker.start()
    def cancel(self):
        if self.worker:self.worker.cancel.set();self.banner.setText('Cancelling the experiment…')
    def worker_done(self):
        worker=self.worker;self.worker=None
        if worker:worker.deleteLater()
        self.compute_button.setEnabled(True);self.cancel_button.setVisible(False)
        if self.closing:QTimer.singleShot(0,self.close)
        else:self.draft()
    def failed(self,error):
        if not self.closing:QMessageBox.warning(self,'Experiment stopped',error)
    def accept_run(self,run):
        if self.run_data:self.previous=self.run_data
        self.run_data=run;self.index=0;self.playhead=0.;self.selected_pick=('edge',0);self.slider.blockSignals(True);self.slider.setRange(0,len(run.times)-1);self.slider.setValue(0);self.slider.blockSignals(False)
        self.replot();self.display(0);self.update_record();self.update_comparison();self.statusBar().showMessage(f'Complete run saved: {run.folder}')
    def replot(self,*_):
        if not self.run_data:return
        self.canvas.index=self.index;self.canvas.terrain=self.terrain.isChecked();self.canvas.setup(self.run_data,self.cutoff.currentData(),self.names.isChecked(),self.background.isChecked());self.canvas.show_draft_restrictions(self.scene);self.update_measurements();self.update_food_table();self.update_comparison()
    def display(self,index):
        if self.run_data is None:return
        self.index=int(index);self.playhead=float(self.run_data.times[self.index]);self.slider.blockSignals(True);self.slider.setValue(self.index);self.slider.blockSignals(False);self.canvas.set_frame(self.index);self.update_measurements()
        self.state_label.setText(f"State {self.index} / {len(self.run_data.times)-1}   ·   t = {self.run_data.times[self.index]:.4g} model units   ·   exact recorded state, no interpolation")
        self.update_food_table();self.picked(*self.selected_pick)
    def update_measurements(self):
        if not self.run_data:return
        r=self.run_data;m=mesh_metrics(r,self.index,self.cutoff.currentData());self.current_metrics=m;diag=r.diagnostics[self.index]
        fraction=m['retained_segments']/len(r.mesh['edges'])
        if self.index==0:self.narrative.setText('Start: every candidate tube is present. Press Play adaptation to watch flow reinforce useful routes while unused tubes decay. Blue and orange mark the current source and sink.')
        else:self.narrative.setText(f"{100*fraction:.1f}% of candidate segments remain above the cutoff. Flow changes as the food pair switches; conductivity remembers earlier flow. {m['largest_food_component']} of {r.food_count} food sources belong to the largest connected component.")
        self.measurements.setText(f"FOOD CONNECTIVITY  {m['largest_food_component']}/{r.food_count} in largest component     |     RETAINED LENGTH  {m['length_km']:.2f} km     |     CONNECTED PAIRS  {100*m['connected_pair_fraction']:.1f}%\nConservation residual {diag[4]:.2e}  ·  backward error {diag[5]:.2e}  ·  scaled rcond estimate {diag[6]:.2e}. Metrics use D ≥ {self.cutoff.currentData():g}; raw D is unchanged.")
    def update_food_table(self):
        r=self.run_data;self.food_table.setRowCount(r.food_count)
        for i,n in enumerate(r.mesh['nodes'][:r.food_count]):
            incident=np.flatnonzero((self.canvas.endpoints==i).any(axis=1));d=r.d[self.index,incident]
            for col,value in enumerate([n['name'],str(self.current_metrics['food_component_sizes'][i]),str(int((d>=self.cutoff.currentData()).sum())),f'{d.max():.5g}',f'{r.p[self.index,i]:.5g}',str(i)]):self.food_table.setItem(i,col,QTableWidgetItem(value))
    def picked(self,kind,k):
        r=self.run_data
        if r is None:return
        self.selected_pick=(kind,k)
        if kind=='food':
            n=r.mesh['nodes'][k];self.selection.setText(f"FOOD {k} · {n['name']} · exact vertex ({n['x']:.4f}, {n['y']:.4f}) km. See Food sources for incident tube values.")
        else:
            e=r.mesh['edges'][k];self.selection.setText(f"TUBE {k} · vertices {e['from']} → {e['to']} · length {e['distance_km']:.3f} km · D {r.d[self.index,k]:.6g} · signed Q {r.q[self.index,k]:.6g} · Δp {r.p[self.index,e['from']]-r.p[self.index,e['to']]:.6g}")
    def pause(self):self.playing=False;self.play.setText('Play adaptation')
    def toggle(self):
        if self.run_data is None:return
        if self.playing:self.pause();return
        if self.index==len(self.run_data.times)-1:self.display(0)
        self.playing=True;self.last_tick=time.monotonic();self.play.setText('Pause')
    def tick(self):
        now=time.monotonic();elapsed=min(.3,now-self.last_tick);self.last_tick=now
        if not self.playing or self.run_data is None:return
        head=min(float(self.run_data.times[-1]),self.playhead+elapsed*self.speed.currentData());index=min(len(self.run_data.times)-1,int(head/self.run_data.settings['dt']))
        if index!=self.index:self.display(index)
        self.playhead=head
        if index==len(self.run_data.times)-1:self.pause()
    def final_state(self):
        if self.run_data:self.pause();self.display(len(self.run_data.times)-1);self.analyze()
    def analyze(self):
        if not self.run_data:return
        m=mesh_metrics(self.run_data,self.index,self.cutoff.currentData(),True)
        route='unavailable: food network disconnected' if m['mean_route_direct_ratio'] is None else f"{m['mean_route_direct_ratio']:.3f} × direct distance"
        self.selection.setText(f"SNAPSHOT ANALYSIS · mean route {route} · length / terminal-only MST {m['length_over_terminal_mst']:.3f} · single-break survival {100*m['single_break_survival']:.1f}% · worst single-break pair accessibility {100*m['worst_break_connected_pair_fraction']:.1f}% · critical bridge length {m['critical_bridge_length_km']:.3f} km. These are defined topology metrics, not the paper’s fault-tolerance statistic.")
    def update_record(self):
        r=self.run_data;s=r.settings
        protocol={'random_pairs':'Uniformly sampled distinct food pairs.','fixed_pair':'One fixed source/sink pair for the whole run.','weighted_pairs':f"Pairs sampled from {len(r.scene.get('weighted_demand',{}).get('pairs',[]))} user-supplied weighted rows. Weights set sampling frequency; each draw still injects the same I₀. Imported weights are not automatically treated as measured demand."}[s['demand_mode']]
        self.record.setHtml(f'''<h2>Pressure, flow and adaptation</h2><p><b>Qᵢⱼ = Dᵢⱼ (pᵢ − pⱼ) / Lᵢⱼ</b><br>At each vertex, net outflow equals imposed current: +I₀ at the source, −I₀ at the sink, zero elsewhere.</p><p><b>dD/dt = |Q|ᵞ / (1 + |Q|ᵞ) − D</b><br>All conductivities update simultaneously with the recorded {s.get('integrator','euler')} integrator. The selected source/sink pair changes every {s['switch_interval']:g} model units; Δt = {s['dt']:g}. A fixed pair is available as a control.</p><p><b>What you see</b><br>All food coordinates are exact graph vertices. Tubes follow actual piecewise-linear mesh edges. Fixed stroke width ∝ D¼ follows the radius relationship for laminar Poiseuille flow at fixed viscosity; no glow, interpolated curves or numerical pruning is used. The display cutoff defines the graph used for displayed connectivity and length. Show the candidate mesh or vary the cutoff to inspect that assumption.</p><p><b>Numerical evidence</b><br>{len(r.mesh['nodes'])} vertices, {len(r.mesh['edges'])} segments, {len(r.times)} states. Scaled sparse LDLᵀ with iterative refinement; every state must pass conservation and backward-error checks. A Hager-style inverse-norm condition estimate is reported; it is not a certified condition bound. Reopening also checks the pressure law, energy identity, recorded integration recurrence and file checksums.</p><p><b>Interpretation</b><br>This implements the sigmoid tube model in <a href="https://doi.org/10.1126/science.1177894">Tero et al., Science (2010)</a>. It starts with a fine mesh like their numerical experiment; it does not reproduce the expanding colony margin in the biological photos. Mesh, initial noise, integration and demand schedule are documented choices. No biological time calibration, measured transport demand, tunnelling physics or railway feasibility is asserted. River crossing resistance is an explicit assumed cost. The terminal-only Euclidean MST is a comparison, not a Steiner lower bound.</p><p><b>Try an experiment</b><br>Play the adaptation, then inspect the final state. Change γ or I₀ while retaining the same seed, mesh and forcing. Compare runs. Refine Δt while retaining the switching interval, and compare different mesh spacings and seeds. Export snapshots at the same cutoff.</p><p>Complete record: {r.folder}</p>''')
        self.record.append(f'<p><b>Recorded forcing protocol</b><br>{protocol}</p>')
        extrema=solver_extrema(r)
        self.record.append(f"<p><b>All accepted pressure solves, including predictor stages</b><br>Maximum conservation residual {extrema['max_conservation']:.4e}; maximum backward error {extrema['max_backward_error']:.4e}; minimum scaled reciprocal-condition estimate {extrema['min_scaled_rcond_estimate']:.4e}.</p>")
        if s.get('integrator','euler')=='heun':
            self.record.append('<p><b>Heun / SSPRK2 stages</b><br>First predict D* = (1−Δt)D + Δt f(Q). Solve a second pressure system at D* using the same held food pair. Correct D_next = ½D + ½[(1−Δt)D* + Δt f(Q*)]. Both stages conserve flow, and all predictor flows/pressures/diagnostics are recorded and independently checked. This is formally second order for smooth held forcing; refine Δt to assess the actual experiment. It does not add biological calibration.</p>')
    def update_comparison(self):
        if self.previous is None or self.run_data is None:return
        cut=self.cutoff.currentData();rows=[]
        a,b=self.previous,self.run_data
        ma,mb=[mesh_metrics(r,len(r.times)-1,cut,True) for r in (a,b)]
        for key in ('integrator','gamma','current','seed','spacing','dt','duration','switch_interval','river_penalty'):rows.append(f'<tr><td>{key}</td><td>{effective_mesh_settings(a.settings)[key]}</td><td>{effective_mesh_settings(b.settings)[key]}</td></tr>')
        for key in ('largest_food_component','length_km','mean_route_direct_ratio','single_break_survival','worst_break_connected_pair_fraction','critical_bridge_length_km','length_over_terminal_mst'):
            def fmt(v):return 'Disconnected' if v is None else f'{v:.5g}'
            rows.append(f'<tr><td>{key}</td><td>{fmt(ma[key])}</td><td>{fmt(mb[key])}</td></tr>')
        self.comparison.setHtml(f'<h2>Final-state comparison · D ≥ {cut:g}</h2><table cellpadding="7"><tr><th>Parameter / measurement</th><th>Previous</th><th>Current</th></tr>{"".join(rows)}</table><p>Differences are exploratory. Isolate one parameter and repeat across seeds, cutoffs and mesh resolutions before drawing conclusions.</p><p>Previous: {a.folder}<br>Current: {b.folder}</p>')
        numerical=compare_mesh_trajectories(a,b)
        if numerical:
            self.comparison.append(f"<h3>Matched numerical trajectories</h3><p>Identical graph, initialization, model parameters and complete held forcing; nested Δt {numerical['coarse_dt']:g} / {numerical['fine_dt']:g}. Methods: {numerical['method_a']} / {numerical['method_b']}.</p><p>Maximum transient |ΔD|: {numerical['max_D_difference']:.6g}<br>Final maximum |ΔD|: {numerical['final_D_max_difference']:.6g}<br>RMS |ΔD| over aligned states and edges: {numerical['rms_D_difference']:.6g}</p><p>This is a finite pairwise comparison, not error against an exact solution or proof that the extracted topology has converged.</p>")
    def open_run(self):
        folder=QFileDialog.getExistingDirectory(self,'Open tube run',str(ROOT/'results/mesh_runs'))
        if folder:
            try:
                r=load_mesh_run(folder);self.scene=copy.deepcopy(r.scene);self.refresh_pairs();self.set_settings(r.settings);self.accept_run(r);self.display(0);self.draft()
            except Exception as error:QMessageBox.warning(self,'Could not open run',str(error))
    def save_design(self):
        path,_=QFileDialog.getSaveFileName(self,'Save experiment design',str(ROOT/'london-tubes.json'),'JSON (*.json)')
        if path:
            try:Path(path).write_text(json.dumps(dict(model='Tero_2010_sigmoid_mesh_v1',scene=self.scene,settings=self.settings()),indent=2)+'\n')
            except Exception as error:QMessageBox.warning(self,'Save failed',str(error))
    def open_design(self):
        path,_=QFileDialog.getOpenFileName(self,'Open experiment design',str(ROOT),'JSON (*.json)')
        if path:
            try:
                try:
                    from .mesh_data import validate_mesh_settings,validate_scene
                except ImportError:from mesh_data import validate_mesh_settings,validate_scene
                obj=json.loads(Path(path).read_text());validate_scene(obj['scene']);validate_mesh_settings(obj['settings'])
                if obj['model']!='Tero_2010_sigmoid_mesh_v1':raise ValueError('This is not a tube experiment design.')
                self.scene=obj['scene'];self.refresh_pairs();self.set_settings(obj['settings']);self.draft()
            except Exception as error:QMessageBox.warning(self,'Could not open design',str(error))
    def import_demand(self):
        path,_=QFileDialog.getOpenFileName(self,'Import relative food-pair frequencies',str(ROOT),'CSV (*.csv)')
        if not path:return
        try:
            try:from .mesh_data import import_pair_weights
            except ImportError:from mesh_data import import_pair_weights
            self.scene=import_pair_weights(self.scene,path);self.mode.setCurrentIndex(self.mode.findData('weighted_pairs'));self.draft()
        except Exception as error:QMessageBox.warning(self,'Demand import failed',str(error))
    def demand_template(self):
        path,_=QFileDialog.getSaveFileName(self,'Save food-pair CSV template',str(ROOT/'food-pair-weights.csv'),'CSV (*.csv)')
        if not path:return
        try:
            foods=[n for n in self.scene['nodes'] if n['kind']=='station']
            with Path(path).open('w',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(['source','sink','weight']);writer.writerow([foods[0]['name'],foods[1]['name'],1]);writer.writerow([foods[1]['name'],foods[2]['name'],1])
            self.statusBar().showMessage('Template uses example relative weights only. Replace with your documented data; select all referenced foods before importing.')
        except Exception as error:QMessageBox.warning(self,'Could not save template',str(error))
    def export(self):
        if self.run_data is None:return
        self.pause();folder=QFileDialog.getExistingDirectory(self,'Choose snapshot export folder',str(self.run_data.folder))
        if folder:
            try:
                target=Path(folder)/f'snapshot-{self.index:05d}-D{self.cutoff.currentData():g}';export_snapshot(self.run_data,self.index,target,self.cutoff.currentData(),self.names.isChecked());self.statusBar().showMessage(f'Exported PNG, SVG, tubes.csv, nodes.csv and snapshot.json: {target}')
            except Exception as error:QMessageBox.warning(self,'Export failed',str(error))
    def open_files(self):
        if self.run_data:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.run_data.folder.resolve())))
    def open_other(self,which):
        if which=='particles':
            try:from .growth_viewer import GrowthViewer
            except ImportError:from growth_viewer import GrowthViewer
            w=GrowthViewer()
        else:
            try:from .viewer import Viewer
            except ImportError:from viewer import Viewer
            w=Viewer()
        self.children_windows.append(w);w.show()
    def closeEvent(self,event):
        self.pause()
        if (self.worker and self.worker.isRunning()) or self.sweep_panel.running():
            self.closing=True
            if self.worker and self.worker.isRunning():self.cancel()
            if self.sweep_panel.running():self.sweep_panel.cancel()
            event.ignore();return
        self.timer.stop();event.accept()
