"""Native geographic experiment workspace; all adaptation remains in C++."""
import copy
import json
from pathlib import Path
import time

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.widgets import RectangleSelector
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
from PySide6.QtCore import Qt,QThread,QTimer,Signal
from PySide6.QtWidgets import (QMainWindow,QWidget,QSplitter,QVBoxLayout,QHBoxLayout,QFormLayout,
    QGroupBox,QLabel,QPushButton,QDoubleSpinBox,QSpinBox,QComboBox,QCheckBox,QSlider,QTabWidget,
    QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QDialog,QDialogButtonBox,QLineEdit,
    QFileDialog,QMessageBox,QInputDialog,QScrollArea,QFrame)
from pyproj import Transformer

try:
    from .spatial_data import ROOT,DEFAULT_SETTINGS,default_scene,build_graph,within_coverage,run_spatial_experiment,load_spatial_run
    from .viewer import Viewer,number
except ImportError:
    from spatial_data import ROOT,DEFAULT_SETTINGS,default_scene,build_graph,within_coverage,run_spatial_experiment,load_spatial_run
    from viewer import Viewer,number


class SpatialWorker(QThread):
    completed=Signal(object)
    failed=Signal(str)
    def __init__(self,scene,settings,parent=None):
        super().__init__(parent);self.scene=copy.deepcopy(scene);self.settings=copy.deepcopy(settings)
    def run(self):
        try:self.completed.emit(run_spatial_experiment(ROOT/'build/physarum_run',self.scene,self.settings))
        except Exception as error:self.failed.emit(str(error))


class StationDialog(QDialog):
    def __init__(self,geography,selected,parent):
        super().__init__(parent);self.setWindowTitle('Select real Tube stations');self.resize(620,650)
        layout=QVBoxLayout(self)
        label=QLabel('Choose 3–80 stations inside the cached central London study area.\nOuter stations are listed for reference and disabled. Coordinates: TfL.');label.setWordWrap(True);layout.addWidget(label)
        search=QLineEdit();search.setPlaceholderText('Filter station names');layout.addWidget(search)
        self.table=QTableWidget(len(geography['station_catalog']),3)
        self.table.setHorizontalHeaderLabels(['Use','Station','TfL ID'])
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row,node in enumerate(geography['station_catalog']):
            checkbox=QTableWidgetItem();checkbox.setFlags(Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsEnabled)
            checkbox.setCheckState(Qt.CheckState.Checked if node['tfl_id'] in selected else Qt.CheckState.Unchecked)
            if not within_coverage(node,geography):
                checkbox.setFlags(Qt.ItemFlag.NoItemFlags);checkbox.setToolTip('Outside cached Thames coverage. Extend the geographic dataset to study this station.')
            self.table.setItem(row,0,checkbox);self.table.setItem(row,1,QTableWidgetItem(node['name']))
            self.table.setItem(row,2,QTableWidgetItem(node['tfl_id']))
        search.textChanged.connect(lambda text:[self.table.setRowHidden(row,text.lower() not in self.table.item(row,1).text().lower()) for row in range(self.table.rowCount())])
        layout.addWidget(self.table)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def selected(self):
        return [self.table.item(row,2).text() for row in range(self.table.rowCount())
                if self.table.item(row,0).checkState()==Qt.CheckState.Checked]


class GeographicFigure(FigureCanvasQTAgg):
    picked=Signal(str,int)
    junction_requested=Signal(float,float)
    barrier_requested=Signal(object)
    def __init__(self):
        self.figure=Figure(figsize=(11,6),dpi=100,layout='constrained',facecolor='white')
        super().__init__(self.figure);self.setMinimumSize(620,360)
        self.run_data=None;self.scene=None;self.edges=[];self.selected_edge=0;self.edit_mode='inspect'
        self.show_elevation=True;self.show_names=False;self.selector=None;self.annotations=[]
        self.mpl_connect('button_press_event',self.on_click)

    def setup(self,scene,edges,run=None):
        self.scene=scene;self.edges=edges;self.run_data=run;self.selected_edge=0
        if self.selector:self.selector.disconnect_events()
        self.figure.clear()
        grid=self.figure.add_gridspec(2,2,width_ratios=[2.2,1])
        self.map=self.figure.add_subplot(grid[:,0]);self.d_plot=self.figure.add_subplot(grid[0,1]);self.q_plot=self.figure.add_subplot(grid[1,1],sharex=self.d_plot)
        self.xy=np.array([[node['x'],node['y']] for node in scene['nodes']])
        elevation=scene['geography']['elevation']
        self.terrain=self.map.pcolormesh(elevation['x'],elevation['y'],elevation['metres'],shading='auto',cmap='gist_earth',alpha=.19,zorder=0)
        self.terrain.set_visible(self.show_elevation)
        self.terrain_bar=self.figure.colorbar(self.terrain,ax=self.map,fraction=.025,pad=.025)
        self.terrain_bar.set_label('Elevation m · sampled context',fontsize=7)
        self.terrain_bar.ax.tick_params(labelsize=7)
        self.terrain_bar.ax.set_visible(self.show_elevation)
        river=LineCollection([way['xy_km'] for way in scene['geography']['river']],colors='#75b3d6',linewidths=3,alpha=.8,zorder=1)
        self.map.add_collection(river)
        for rect in scene['barriers']:
            x0,y0,x1,y1=rect;self.map.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor='#a14d4d',alpha=.17,hatch='//',edgecolor='#a14d4d',zorder=2))
        segments=[self.xy[[e['from'],e['to']]] for e in edges]
        self.map.add_collection(LineCollection(segments,colors='#c9cfd1',linewidths=.45,alpha=.55,zorder=2))
        self.links=LineCollection(segments,colors='#253b4d',linewidths=.7,alpha=.85,zorder=3)
        self.map.add_collection(self.links)
        stations=np.array([node['kind']=='station' for node in scene['nodes']])
        self.map.scatter(self.xy[stations,0],self.xy[stations,1],s=18,facecolor='white',edgecolors='#243b4a',linewidths=.7,zorder=5)
        self.map.scatter(self.xy[~stations,0],self.xy[~stations,1],s=18,marker='+',color='#606b72',zorder=5)
        self.terminals=self.map.scatter([np.nan,np.nan],[np.nan,np.nan],s=65,c=['#087f8c','#c35b2d'],edgecolors='white',linewidths=1,zorder=7)
        self.selection=self.map.scatter([],[],s=90,facecolors='none',edgecolors='#d39300',linewidths=1.5,zorder=8)
        self.annotation=self.map.annotate('',xy=(0,0),xytext=(8,10),textcoords='offset points',fontsize=8,
                                          bbox={'boxstyle':'round,pad=.3','fc':'white','ec':'#aaa','alpha':.95},zorder=10)
        self.annotation.set_visible(False)
        self.annotations=[]
        for i,node in enumerate(scene['nodes']):
            self.annotations.append(self.map.annotate(node['name'],self.xy[i],xytext=(4,5),textcoords='offset points',fontsize=6.5,color='#333',visible=self.show_names))
        self.map.set_aspect('equal');self.map.set_xlim(self.xy[:,0].min()-1,self.xy[:,0].max()+1);self.map.set_ylim(self.xy[:,1].min()-1,self.xy[:,1].max()+1)
        self.map.set_xlabel('British National Grid easting (km)',fontsize=8);self.map.set_ylabel('Northing (km)',fontsize=8)
        self.map.tick_params(labelsize=8);self.map.grid(alpha=.1,lw=.5)
        self.map.set_title('London · real station coordinates · possible new connections',fontsize=10,loc='left')
        self.map.text(.01,.01,'TfL station data · © OpenStreetMap contributors\nElevation: Copernicus / Open-Meteo (visual context only)',transform=self.map.transAxes,fontsize=6.5,
                      va='bottom',color='#444',bbox={'facecolor':'white','alpha':.8,'edgecolor':'none'},zorder=11)
        self.selector=RectangleSelector(self.map,self.on_rectangle,useblit=False,button=[1],minspanx=.1,minspany=.1,spancoords='data',interactive=False)
        self.selector.set_active(self.edit_mode=='barrier')
        self.edge_d,=self.d_plot.plot([],[],color='#245f8a',lw=1.2,label='Selected connection')
        self.mean_d,=self.d_plot.plot([],[],color='#777',lw=.9,ls='--',label='Mean across connections')
        self.edge_q,=self.q_plot.plot([],[],color='#245f8a',lw=1)
        self.cursors=[axis.axvline(0,color='#444',ls='--',lw=.7) for axis in (self.d_plot,self.q_plot)]
        self.markers=[axis.plot([],[],'o',color='#c35b2d',ms=4)[0] for axis in (self.d_plot,self.q_plot)]
        for axis,label in ((self.d_plot,'Conductivity D'),(self.q_plot,'Signed flow Q')):
            axis.set_ylabel(label,fontsize=8);axis.tick_params(labelsize=7);axis.grid(alpha=.2,lw=.5);axis.spines[['top','right']].set_visible(False)
        self.q_plot.set_xlabel('Model time (arbitrary units)',fontsize=8)
        self.d_plot.legend(fontsize=6.5,frameon=False,loc='best')
        self.d_plot.set_title('Click a connection to inspect it',fontsize=9,loc='left')
        if run:self.set_selected_edge(0);self.set_frame(0)
        else:
            self.terminals.set_offsets(np.empty((0,2)));self.map.set_title('Scenario preview · Run adaptation to compute flows',fontsize=10,loc='left')
        self.draw_idle()

    def set_selected_edge(self,index):
        self.selected_edge=int(index)
        if not self.run_data:return
        run=self.run_data;i=self.selected_edge
        self.edge_d.set_data(run.times,run.d[:,i]);self.mean_d.set_data(run.times,run.d.mean(axis=1));self.edge_q.set_data(run.times,run.q[:,i])
        for axis in (self.d_plot,self.q_plot):axis.relim();axis.autoscale_view();axis.set_xlim(0,run.times[-1])
        self.d_plot.set_ylim(bottom=0)
        self.draw_idle()

    def set_frame(self,index):
        if not self.run_data:return
        run=self.run_data
        # Fixed visual mapping for all frames: 6 points * sqrt(D / 0.5).
        widths=6*np.sqrt(run.d[index]/.5);widths[run.d[index]<1e-10]=0
        self.links.set_linewidths(widths)
        source,sink=run.sources[index],run.sinks[index]
        self.terminals.set_offsets(self.xy[[source,sink]])
        for cursor in self.cursors:cursor.set_xdata([run.times[index]]*2)
        self.markers[0].set_data([run.times[index]],[run.d[index,self.selected_edge]])
        self.markers[1].set_data([run.times[index]],[run.q[index,self.selected_edge]])
        colors=['#253b4d']*len(self.edges);colors[self.selected_edge]='#b57d00';self.links.set_colors(colors)
        self.draw_idle()

    def on_rectangle(self,start,end):
        if self.edit_mode=='barrier' and start.xdata is not None and end.xdata is not None:
            self.barrier_requested.emit([min(start.xdata,end.xdata),min(start.ydata,end.ydata),max(start.xdata,end.xdata),max(start.ydata,end.ydata)])

    def on_click(self,event):
        if event.inaxes is not getattr(self,'map',None) or event.xdata is None or event.button!=1:return
        if self.toolbar and self.toolbar.mode:return
        if self.edit_mode=='junction':
            self.junction_requested.emit(event.xdata,event.ydata);return
        if self.edit_mode=='barrier':return
        pixel=self.map.transData.transform(self.xy)
        distance=np.linalg.norm(pixel-np.array([event.x,event.y]),axis=1)
        node=int(distance.argmin())
        if distance[node]<11:
            self.selection.set_offsets(self.xy[[node]])
            self.annotation.xy=self.xy[node];self.annotation.set_text(self.scene['nodes'][node]['name']);self.annotation.set_visible(True)
            self.picked.emit('node',node);self.draw_idle();return
        if self.edges:
            a=np.array([pixel[e['from']] for e in self.edges]);b=np.array([pixel[e['to']] for e in self.edges])
            delta=b-a;relative=np.array([event.x,event.y])-a
            fraction=np.clip(np.sum(relative*delta,axis=1)/np.sum(delta*delta,axis=1),0,1)
            nearest=np.linalg.norm(relative-fraction[:,None]*delta,axis=1);edge=int(nearest.argmin())
            if nearest[edge]<8:self.picked.emit('edge',edge)


class SpatialViewer(QMainWindow):
    def __init__(self,auto_run=True):
        super().__init__();self.setWindowTitle('Physarum Spatial Explorer — London (experimental)');self.resize(1460,920);self.setMinimumSize(1120,730)
        self.scene=default_scene();self.run_data=None;self.worker=None;self.index=0;self.selected_edge=0
        self.selected_item=None
        self.playing=False;self.playhead=0.;self.last_tick=time.monotonic();self.controls={};self.previous_windows=[]
        self.build_ui();self.refresh_station_choices();self.preview()
        self.timer=QTimer(self);self.timer.setInterval(50);self.timer.timeout.connect(self.tick);self.timer.start()
        if auto_run:QTimer.singleShot(0,self.run)

    def build_ui(self):
        file=self.menuBar().addMenu('File');self.file_menu=file
        file.addAction('Open spatial run folder…').triggered.connect(self.open_run)
        file.addAction('Open saved scenario…').triggered.connect(self.open_scene)
        file.addAction('Save scenario…').triggered.connect(self.save_scene)
        file.addSeparator();file.addAction('Open validated four-node viewer').triggered.connect(self.open_baseline)
        self.menuBar().addMenu('Help').addAction('How to read this experiment…').triggered.connect(self.help)
        split=QSplitter(Qt.Orientation.Horizontal);left=QWidget();formbox=QVBoxLayout(left);formbox.setContentsMargins(12,12,12,12)
        self.station_summary=QLabel();self.station_summary.setWordWrap(True);formbox.addWidget(self.station_summary)
        self.choose_button=QPushButton('Choose Tube stations…');self.choose_button.clicked.connect(self.choose_stations);formbox.addWidget(self.choose_button)
        group=QGroupBox('Network and demand');form=QFormLayout(group)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.mode=QComboBox();self.mode.addItem('Uniform pairs (synthetic)','uniform_pairs');self.mode.addItem('One fixed pair','fixed_pair');form.addRow('Demand',self.mode)
        self.source=QComboBox();self.sink=QComboBox()
        for combo in (self.mode,self.source,self.sink):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);combo.setMinimumContentsLength(14)
        form.addRow('Fixed source',self.source);form.addRow('Fixed sink',self.sink)
        self.mode.currentIndexChanged.connect(self.update_mode)
        self.source.currentIndexChanged.connect(self.controls_changed);self.sink.currentIndexChanged.connect(self.controls_changed)
        specs=[('neighbours','Candidate neighbours',2,12,1,0),('river_penalty','Thames penalty [km eq.]',0,10,.5,2),
               ('current','Injected flow I₀',.1,5,.1,2),('gamma','Response γ',.5,3,.1,2),('dt','Time step Δt',.01,.25,.01,3),
               ('duration','Duration',1,40,1,2),('seed','Demand seed',0,2**31-1,1,0)]
        for key,label,low,high,step,decimals in specs:
            field=QSpinBox() if decimals==0 else QDoubleSpinBox()
            field.setRange(low,high);field.setSingleStep(step)
            if decimals:field.setDecimals(decimals)
            field.setValue(DEFAULT_SETTINGS[key]);field.setObjectName(key);self.controls[key]=field;form.addRow(label,field)
        self.controls['river_penalty'].setToolTip('Assumed extra effective length for any link crossing the Thames centreline. Not a measured tunnelling cost.')
        formbox.addWidget(group)
        self.run_button=QPushButton('Run adaptation');self.run_button.setObjectName('run_spatial');self.run_button.clicked.connect(self.run);formbox.addWidget(self.run_button)
        self.reset_button=QPushButton('Restore London example');self.reset_button.clicked.connect(self.reset_scene);formbox.addWidget(self.reset_button)
        editing=QGroupBox('Scenario editing');edit=QVBoxLayout(editing)
        self.edit_mode=QComboBox();self.edit_mode.addItem('Inspect stations / links','inspect');self.edit_mode.addItem('Click to add a junction','junction');self.edit_mode.addItem('Drag a restricted rectangle','barrier')
        self.edit_mode.currentIndexChanged.connect(self.update_edit_mode);edit.addWidget(self.edit_mode)
        clear=QPushButton('Clear user restrictions');clear.clicked.connect(self.clear_barriers);edit.addWidget(clear)
        self.clear_button=clear
        self.terrain_box=QCheckBox('Show elevation context (not a cost)');self.terrain_box.setChecked(True);self.terrain_box.toggled.connect(self.toggle_terrain);edit.addWidget(self.terrain_box)
        self.names_box=QCheckBox('Show all station names');self.names_box.toggled.connect(self.toggle_names);edit.addWidget(self.names_box)
        formbox.addWidget(editing)
        info=QLabel('Grey lines: possible connections.\nDark widths: adapted conductivity.\nBlue/orange nodes: current source/sink.\n\nChanging demand is synthetic. Surface elevation is context only. This is not a Tube engineering design.');info.setWordWrap(True);formbox.addWidget(info)
        formbox.addStretch()
        scroll=QScrollArea();scroll.setWidget(left);scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame);scroll.setMinimumWidth(350);split.addWidget(scroll)
        right=QWidget();layout=QVBoxLayout(right);layout.setContentsMargins(2,10,10,10)
        self.title=QLabel();self.title.setWordWrap(True);layout.addWidget(self.title)
        vertical=QSplitter(Qt.Orientation.Vertical);figure_container=QWidget();figure_layout=QVBoxLayout(figure_container);figure_layout.setContentsMargins(0,0,0,0)
        self.canvas=GeographicFigure();self.canvas.picked.connect(self.pick);self.canvas.junction_requested.connect(self.add_junction);self.canvas.barrier_requested.connect(self.add_barrier)
        self.toolbar=NavigationToolbar2QT(self.canvas,self);figure_layout.addWidget(self.toolbar);figure_layout.addWidget(self.canvas);vertical.addWidget(figure_container)
        tabs=QTabWidget();self.edge_table=QTableWidget();self.edge_table.setColumnCount(6);self.edge_table.setHorizontalHeaderLabels(['Connection','Distance km','Cost km eq.','Crosses Thames','D','Signed Q'])
        self.edge_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.edge_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.edge_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.edge_table.itemSelectionChanged.connect(self.table_pick);tabs.addTab(self.edge_table,'Connections')
        self.notes=QLabel();self.notes.setWordWrap(True);self.notes.setMargin(14);self.notes.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);tabs.addTab(self.notes,'Checks and interpretation')
        vertical.addWidget(tabs);vertical.setSizes([570,190]);layout.addWidget(vertical,1)
        buttons=QHBoxLayout();self.play_button=QPushButton('Play');self.play_button.clicked.connect(self.toggle_play);buttons.addWidget(self.play_button)
        restart=QPushButton('Restart');restart.clicked.connect(lambda:self.scrub(0));buttons.addWidget(restart)
        next_step=QPushButton('Step +1');next_step.clicked.connect(lambda:self.scrub(self.index+1));buttons.addWidget(next_step)
        buttons.addStretch();buttons.addWidget(QLabel('Playback:'));self.speed=QComboBox()
        for speed in (.25,.5,1,2,4):self.speed.addItem(f'{speed:g} model units/s',float(speed))
        self.speed.setCurrentIndex(2);buttons.addWidget(self.speed);layout.addLayout(buttons)
        self.timeline=QSlider(Qt.Orientation.Horizontal);self.timeline.setRange(0,400);self.timeline.valueChanged.connect(self.scrub);layout.addWidget(self.timeline)
        bottom=QHBoxLayout();bottom.addWidget(QLabel('Step:'));self.step_spin=QSpinBox();self.step_spin.setRange(0,400);self.step_spin.valueChanged.connect(self.scrub);bottom.addWidget(self.step_spin)
        self.time_label=QLabel();bottom.addWidget(self.time_label);bottom.addStretch();self.selection_label=QLabel('Click a station or connection.');bottom.addWidget(self.selection_label);layout.addLayout(bottom)
        split.addWidget(right);split.setSizes([350,1110]);self.setCentralWidget(split)
        self.statusBar().showMessage('London geography loaded. Station-pair demand and crossing costs are explicit assumptions.')
        for field in self.controls.values():field.valueChanged.connect(self.controls_changed)

    def settings(self):
        settings=dict(DEFAULT_SETTINGS)
        settings.update({key:field.value() for key,field in self.controls.items()})
        settings.update(demand_mode=self.mode.currentData(),source_id=self.source.currentData(),sink_id=self.sink.currentData())
        return settings

    def update_mode(self):
        fixed=self.mode.currentData()=='fixed_pair';self.source.setEnabled(fixed);self.sink.setEnabled(fixed)
        self.controls_changed()

    def refresh_station_choices(self):
        for combo,default in ((self.source,DEFAULT_SETTINGS['source_id']),(self.sink,DEFAULT_SETTINGS['sink_id'])):
            old=combo.currentData() or default;combo.blockSignals(True);combo.clear()
            for node in self.scene['nodes']:
                if node['kind']=='station':combo.addItem(node['name'],node['key'])
            index=combo.findData(old);combo.setCurrentIndex(index if index>=0 else (0 if combo is self.source else max(0,combo.count()-1)))
            combo.blockSignals(False)
        self.update_mode()

    def controls_changed(self):
        if self.run_data:self.statusBar().showMessage('Settings changed. Display still shows the recorded run; Run adaptation to apply the controls.')

    def preview(self):
        self.pause();self.run_data=None;self.timeline.setEnabled(False);self.step_spin.setEnabled(False);self.play_button.setEnabled(False)
        self.selected_item=None;self.selection_label.setText('Click a station or connection.')
        try:edges,_=build_graph(self.scene,self.settings())
        except ValueError as error:edges=[];self.statusBar().showMessage(str(error))
        self.canvas.setup(self.scene,edges);self.toolbar.update();self.edge_table.setRowCount(0)
        stations=sum(node['kind']=='station' for node in self.scene['nodes'])
        self.station_summary.setText(f'{stations} real TfL stations\n{len(self.scene["nodes"])-stations} user junctions')
        self.title.setText(f'SCENARIO PREVIEW · {len(edges)} candidate connections · Run adaptation to compute a new experiment')
        self.notes.setText('No computed states are displayed in this preview. Geographical coordinates and candidate links are inputs.\n\nElevation shading is visual context. Restricted rectangles are user assumptions. New connections are straight segments between nodes, not proposed alignments or existing tracks.')
        self.time_label.setText('No run loaded')

    def run(self):
        if self.worker and self.worker.isRunning():return
        self.pause();self.run_button.setEnabled(False);self.choose_button.setEnabled(False);self.edit_mode.setEnabled(False);self.reset_button.setEnabled(False);self.clear_button.setEnabled(False)
        for control in self.controls.values():control.setEnabled(False)
        self.mode.setEnabled(False);self.source.setEnabled(False);self.sink.setEnabled(False);self.file_menu.setEnabled(False)
        self.statusBar().showMessage('Preparing the spatial graph and running the C++ model…')
        self.worker=SpatialWorker(self.scene,self.settings(),self)
        self.worker.completed.connect(self.set_run);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.finished);self.worker.start()

    def finished(self):
        for widget in (self.run_button,self.choose_button,self.edit_mode,self.reset_button,self.clear_button):widget.setEnabled(True)
        for control in self.controls.values():control.setEnabled(True)
        self.mode.setEnabled(True);self.file_menu.setEnabled(True)
        fixed=self.mode.currentData()=='fixed_pair';self.source.setEnabled(fixed);self.sink.setEnabled(fixed)

    def failed(self,message):
        QMessageBox.warning(self,'Experiment could not complete',message);self.statusBar().showMessage('Run failed. Inputs and partial output, if any, were retained.')

    def set_run(self,run):
        self.pause();self.run_data=run;self.scene=copy.deepcopy(run.scene);self.index=0;self.playhead=0.;self.selected_edge=0
        self.selected_item=None;self.selection_label.setText('Click a station or connection.')
        self.canvas.setup(self.scene,run.edges,run);self.toolbar.update();self.refresh_station_choices()
        for key,field in self.controls.items():
            field.blockSignals(True);field.setValue(run.settings[key]);field.blockSignals(False)
        self.mode.blockSignals(True);self.mode.setCurrentIndex(self.mode.findData(run.settings['demand_mode']));self.mode.blockSignals(False)
        self.source.setCurrentIndex(self.source.findData(run.settings['source_id']));self.sink.setCurrentIndex(self.sink.findData(run.settings['sink_id']));self.update_mode()
        self.timeline.setRange(0,len(run.times)-1);self.step_spin.setRange(0,len(run.times)-1)
        self.timeline.setEnabled(True);self.step_spin.setEnabled(True);self.play_button.setEnabled(True)
        self.edge_table.blockSignals(True);self.edge_table.setRowCount(len(run.edges))
        for edge in run.edges:
            i=edge['id'];label=f'{self.scene["nodes"][edge["from"]]["name"]} → {self.scene["nodes"][edge["to"]]["name"]}'
            for col,value in enumerate((label,number(edge['distance_km']),number(edge['length']),'yes' if edge['river_crossing'] else 'no','','')):
                item=QTableWidgetItem(value);item.setToolTip(value);self.edge_table.setItem(i,col,item)
        self.edge_table.blockSignals(False)
        count=sum(node['kind']=='station' for node in self.scene['nodes'])
        self.station_summary.setText(f'{count} TfL stations · {len(run.edges)} links\n{len(self.scene["nodes"])-count} user junctions')
        demand='uniform synthetic station pairs' if run.settings['demand_mode']=='uniform_pairs' else 'one fixed source/sink'
        self.title.setText(f'RECORDED C++ RUN · {demand} · seed {run.settings["seed"]} · Thames penalty +{run.settings["river_penalty"]:g} km eq. (assumed)')
        try:location=run.folder.relative_to(ROOT)
        except ValueError:location=run.folder
        self.statusBar().showMessage(f'Automatically saved: {location}')
        self.display_frame(0)

    def display_frame(self,index):
        run=self.run_data
        if run is None:return
        self.index=max(0,min(int(index),len(run.times)-1));i=self.index
        self.canvas.set_frame(i)
        for widget in (self.timeline,self.step_spin):widget.blockSignals(True);widget.setValue(i);widget.blockSignals(False)
        a,b=self.scene['nodes'][run.sources[i]]['name'],self.scene['nodes'][run.sinks[i]]['name']
        self.time_label.setText(f't = {run.times[i]:.2f} / {run.times[-1]:g} · {a} → {b}')
        self.edge_table.blockSignals(True)
        for edge in run.edges:
            row=edge['id'];self.edge_table.item(row,4).setText(number(run.d[i,row]));self.edge_table.item(row,5).setText(number(run.q[i,row]))
        self.edge_table.blockSignals(False)
        self.update_selection_label()
        self.notes.setText(f'Current pair: {a} → {b}\nFlow conservation residual: {run.diagnostics[i,0]:.3e} (max across run {run.diagnostics[:,0].max():.3e})\n'
            f'Pressure backward error: {run.diagnostics[i,1]:.3e}\nScaled reciprocal condition estimate: {run.diagnostics[i,2]:.3e}\n\n'
            'The imported record was checked against conservation, Q = D/C × pressure difference and every Euler update. '
            'Candidate cost C = straight-line distance + assumed river-crossing penalty. Elevation is context only. '
            'Uniform pair selection is not measured passenger demand. No capacity, journey-time, interchange or tunnelling/geology model is included.')

    def pick(self,kind,index):
        self.selected_item=(kind,index)
        if kind=='edge' and self.run_data:
            self.selected_edge=index;self.canvas.set_selected_edge(index);self.canvas.set_frame(self.index)
            self.edge_table.blockSignals(True);self.edge_table.selectRow(index);self.edge_table.scrollToItem(self.edge_table.item(index,0));self.edge_table.blockSignals(False)
        self.update_selection_label()

    def update_selection_label(self):
        if self.selected_item is None:return
        kind,index=self.selected_item
        if kind=='node':
            node=self.scene['nodes'][index];self.selection_label.setText(node['name']+(' · TfL station' if node['kind']=='station' else ' · hypothetical junction'))
            if self.run_data:self.selection_label.setText(self.selection_label.text()+f' · p={number(self.run_data.p[self.index,index])}')
        elif self.run_data:
            self.selection_label.setText(f'Connection {index}: D={number(self.run_data.d[self.index,index])}, Q={number(self.run_data.q[self.index,index])}')

    def table_pick(self):
        if self.run_data and self.edge_table.currentRow()>=0:self.pick('edge',self.edge_table.currentRow())

    def pause(self):self.playing=False;self.play_button.setText('Play')
    def toggle_play(self):
        if self.run_data is None:return
        if self.playing:self.pause();return
        if self.index==len(self.run_data.times)-1:self.display_frame(0)
        self.playhead=self.run_data.times[self.index];self.last_tick=time.monotonic();self.playing=True;self.play_button.setText('Pause')
    def scrub(self,index):
        self.pause();self.display_frame(index)
        if self.run_data is not None:self.playhead=self.run_data.times[self.index]
    def tick(self):
        now=time.monotonic();elapsed=min(now-self.last_tick,.25);self.last_tick=now
        if not self.playing or self.run_data is None:return
        self.playhead=min(self.playhead+elapsed*self.speed.currentData(),self.run_data.times[-1])
        index=min(int((self.playhead+1e-9)/self.run_data.settings['dt']),len(self.run_data.times)-1)
        if index!=self.index:self.display_frame(index)
        if index==len(self.run_data.times)-1:self.pause()

    def choose_stations(self):
        dialog=StationDialog(self.scene['geography'],{node['tfl_id'] for node in self.scene['nodes'] if node['kind']=='station'},self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        keys=dialog.selected()
        if not 3<=len(keys)<=80:QMessageBox.warning(self,'Station count','Choose 3–80 stations.');return
        lookup={node['tfl_id']:node for node in self.scene['geography']['station_catalog']}
        nodes=[]
        for key in keys:node=copy.deepcopy(lookup[key]);node['key']=key;nodes.append(node)
        self.scene['nodes']=nodes+[node for node in self.scene['nodes'] if node['kind']=='junction']
        self.refresh_station_choices();self.preview()

    def update_edit_mode(self):
        self.canvas.edit_mode=self.edit_mode.currentData()
        if self.canvas.selector:self.canvas.selector.set_active(self.canvas.edit_mode=='barrier')
        if self.canvas.edit_mode!='inspect':self.pause();self.statusBar().showMessage('Edit the scenario on the map. Edits create a preview; run again to compute new states.')

    def add_junction(self,x,y):
        if self.worker and self.worker.isRunning():return
        if len(self.scene['nodes'])>=100:QMessageBox.warning(self,'Node limit','This viewer supports at most 100 nodes.');return
        name,ok=QInputDialog.getText(self,'Hypothetical junction','Name (no passenger demand is assigned):',text=f'Junction {1+sum(node["kind"]=="junction" for node in self.scene["nodes"])}')
        if not ok:return
        lon,lat=Transformer.from_crs(27700,4326,always_xy=True).transform(x*1000,y*1000)
        node={'key':f'junction-{time.time_ns()}','name':name or 'Junction','kind':'junction','x':x,'y':y,'lon':lon,'lat':lat,'coordinate_source':'user hypothesis'}
        if not within_coverage(node,self.scene['geography']):
            QMessageBox.warning(self,'Outside cached geography','Place junctions inside the cached central London study area. Outer London needs an extended geographic dataset.');return
        self.scene['nodes'].append(node)
        self.preview()

    def add_barrier(self,rect):
        if self.worker and self.worker.isRunning():return
        self.scene['barriers'].append(rect);self.preview()
    def clear_barriers(self):self.scene['barriers']=[];self.preview()
    def reset_scene(self):
        self.scene=default_scene()
        for key,field in self.controls.items():field.setValue(DEFAULT_SETTINGS[key])
        self.mode.setCurrentIndex(0);self.edit_mode.setCurrentIndex(0);self.refresh_station_choices()
        self.source.setCurrentIndex(self.source.findData(DEFAULT_SETTINGS['source_id']));self.sink.setCurrentIndex(self.sink.findData(DEFAULT_SETTINGS['sink_id']));self.preview()
    def toggle_terrain(self,value):
        self.canvas.show_elevation=value
        if hasattr(self.canvas,'terrain'):
            self.canvas.terrain.set_visible(value);self.canvas.terrain_bar.ax.set_visible(value);self.canvas.draw_idle()
    def toggle_names(self,value):
        self.canvas.show_names=value
        for label in self.canvas.annotations:label.set_visible(value)
        self.canvas.draw_idle()

    def open_run(self):
        folder=QFileDialog.getExistingDirectory(self,'Open auto-saved spatial run',str(ROOT/'results/spatial_runs'))
        if not folder:return
        try:self.set_run(load_spatial_run(folder))
        except Exception as error:QMessageBox.warning(self,'Invalid spatial run',str(error))
    def save_scene(self):
        path,_=QFileDialog.getSaveFileName(self,'Save scenario','london-scenario.json','Scenario (*.json)')
        if path:Path(path).write_text(json.dumps({'scene':self.scene,'settings':self.settings()},indent=2,ensure_ascii=False)+'\n')
    def open_scene(self):
        path,_=QFileDialog.getOpenFileName(self,'Open scenario','','Scenario (*.json)')
        if not path:return
        try:
            data=json.loads(Path(path).read_text());build_graph(data['scene'],data['settings']);self.scene=data['scene']
            for key,field in self.controls.items():field.setValue(data['settings'][key])
            self.refresh_station_choices();self.mode.setCurrentIndex(self.mode.findData(data['settings']['demand_mode']))
            self.source.setCurrentIndex(self.source.findData(data['settings']['source_id']));self.sink.setCurrentIndex(self.sink.findData(data['settings']['sink_id']));self.preview()
        except Exception as error:QMessageBox.warning(self,'Invalid scenario',str(error))
    def open_baseline(self):
        window=Viewer();window.show();self.previous_windows.append(window)
    def help(self):
        QMessageBox.information(self,'Reading the London experiment',
            '1. Choose real Tube stations. Grey links are the possible new connections, generated from nearby nodes. They are not existing Tube lines.\n\n'
            '2. Run adaptation. Uniform mode samples two demand stations per numerical update, using a recorded seeded schedule. Junctions carry no external demand.\n\n'
            '3. Press Play. Width is 6 points × sqrt(D/0.5); it uses one fixed scale throughout the run. Links below D=1e-10 have only their pale outline. Every raw value is retained.\n\n'
            '4. Click a station for its name and pressure, or a connection for its D/Q history. Blue and orange nodes identify the current source and sink.\n\n'
            '5. Try a different Thames penalty with the same seed. The penalty is an assumed km-equivalent cost, not a measured tunnel cost. Elevation shading does not affect flow.\n\n'
            'User rectangles exclude initial candidate segments; they are hypothetical restrictions. Intersecting lines are not junctions unless a node is present. All runs are saved automatically with inputs, demand schedule, costs and source geography.\n\n'
            'This does not model real passenger demand, capacity, service patterns, tunnel geology, economics or engineering feasibility. It is a geographic experiment using an established abstract model.')
    def closeEvent(self,event):
        self.timer.stop()
        if self.worker and self.worker.isRunning():self.worker.wait(95000)
        event.accept()
