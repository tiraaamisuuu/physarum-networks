"""Native observation workspace for the separately documented particle growth model."""
import copy
import json
from pathlib import Path
import threading
import time

import numpy as np
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
from PySide6.QtCore import Qt,QTimer,QThread,Signal
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QGroupBox,QLabel,
    QComboBox,QPushButton,QSpinBox,QDoubleSpinBox,QCheckBox,QSlider,QSplitter,QScrollArea,QFrame,
    QFileDialog,QMessageBox,QDialog)

try:
    from .growth_data import ROOT,DEFAULT_GROWTH,default_scene,prepare_growth,run_growth_experiment,load_growth_run
    from .spatial_viewer import StationDialog,SpatialViewer
    from .viewer import Viewer
except ImportError:
    from growth_data import ROOT,DEFAULT_GROWTH,default_scene,prepare_growth,run_growth_experiment,load_growth_run
    from spatial_viewer import StationDialog,SpatialViewer
    from viewer import Viewer

FIELD_COLOURS=['#101c24','#4f3525','#bc7a18','#f6d55b','#fff2b0']


def explain_growth(run,index):
    """Plain-language interpretation of measured counters, never inferred optimality."""
    tick=int(run.stats[index,1]);visited=int(run.stats[index,3]);total=len(run.foods)
    if index==0:
        return ('A small starting patch',
            'The colony is only at the starting station. The pale dots elsewhere are food sites. '
            'No routes have been drawn between them. Press Play growth to watch the recorded experiment.')
    if visited<max(3,total//4):
        return ('Exploring the neighbourhood',
            'Tiny simulated particles move out from the patch. Each senses ahead, left and right, '
            'turns toward stronger food or trail cues, and leaves a trail as it moves. Local division expands the colony.')
    if visited<total:
        return ('Finding food and branching',
            f'Live particles have reached {visited} of {total} food sites by update {tick}. '
            'Shared trails attract more movement, so branches and loops emerge. Green dots mark sites visited at least once.')
    return ('Redistributing the network',
        f'All {total} sites have been visited at least once. Food cues weaken after first contact. '
        'Particles keep moving; abandoned trails fade, and crowded regions lose particles. '
        'A visited site may later lose its visible connection. This is not proof of a connected or optimal railway.')


class GrowthWorker(QThread):
    completed=Signal(object);failed=Signal(str)
    def __init__(self,scene,settings,parent=None):
        super().__init__(parent);self.scene=copy.deepcopy(scene);self.settings=copy.deepcopy(settings);self.cancel=threading.Event()
    def run(self):
        try:
            result=run_growth_experiment(self.scene,self.settings,cancel=self.cancel)
            if not self.cancel.is_set():self.completed.emit(result)
        except Exception as error:self.failed.emit(str(error))


class GrowthFigure(FigureCanvasQTAgg):
    food_picked=Signal(int)
    def __init__(self):
        self.figure=Figure(figsize=(11,7),dpi=100,layout='constrained',facecolor='white');super().__init__(self.figure)
        self.setMinimumSize(640,430);self.run_data=None;self.show_names=False;self.show_agents=False;self.selected=None
        self.cmap=LinearSegmentedColormap.from_list('physarum_activity',FIELD_COLOURS)
        self.mpl_connect('button_press_event',self.pick)

    def setup(self,scene,settings,run=None):
        foods,pixels,extent,blocked,river,config=prepare_growth(scene,settings)
        self.run_data=run;self.scene=scene;self.foods=foods;self.extent=extent;self.selected=None
        self.figure.clear();grid=self.figure.add_gridspec(2,2,height_ratios=[4.5,1])
        self.map=self.figure.add_subplot(grid[0,:]);self.reached_plot=self.figure.add_subplot(grid[1,0]);self.population_plot=self.figure.add_subplot(grid[1,1],sharex=self.reached_plot)
        self.map.set_facecolor(FIELD_COLOURS[0]);self.map.set_aspect('equal')
        self.image=self.map.imshow(np.zeros(blocked.shape),origin='lower',extent=extent,cmap=self.cmap,vmin=0,vmax=15,interpolation='nearest',zorder=1)
        self.agent_image=self.map.imshow(np.zeros((*blocked.shape,4)),origin='lower',extent=extent,interpolation='nearest',zorder=2)
        self.agent_image.format_cursor_data=lambda data:''
        river_lines=LineCollection([way['xy_km'] for way in scene['geography']['river']],colors='#638ea4',linewidths=1.4,alpha=.6,zorder=3);self.map.add_collection(river_lines)
        for x0,y0,x1,y1 in scene['barriers']:
            self.map.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor='#6f3b46',edgecolor='#d8a5ac',alpha=.6,hatch='//',zorder=4))
        self.xy=np.array([[node['x'],node['y']] for node in foods])
        self.sites=self.map.scatter(self.xy[:,0],self.xy[:,1],s=22,facecolors='#f1eee0',edgecolors='#101c24',linewidths=.6,zorder=6)
        start=next(i for i,n in enumerate(foods) if n['key']==settings['start_id']);self.start=start
        self.map.scatter(*self.xy[start],s=150,facecolors='none',edgecolors='#f1d680',linewidths=1.1,zorder=7)
        name=foods[start]['name']
        self.map.annotate('START · '+name,self.xy[start],xytext=(8,14),textcoords='offset points',fontsize=8,color='#fff2b0',zorder=8,
                          bbox={'fc':'#101c24','ec':'none','alpha':.85,'pad':3})
        self.selection=self.map.scatter([],[],s=130,facecolors='none',edgecolors='#ffffff',linewidths=1,zorder=9)
        self.annotation=self.map.annotate('',(0,0),xytext=(8,-18),textcoords='offset points',fontsize=8,color='white',visible=False,zorder=10,
            bbox={'fc':'#101c24','ec':'#7e8b91','alpha':.95,'pad':4})
        self.names=[self.map.annotate(n['name'],self.xy[i],xytext=(4,5),textcoords='offset points',color='#e4e4dd',fontsize=6.5,visible=self.show_names,zorder=8) for i,n in enumerate(foods)]
        self.map.set_xlim(extent[:2]);self.map.set_ylim(extent[2:]);self.map.set_xlabel('British National Grid easting (km)',fontsize=8);self.map.set_ylabel('Northing (km)',fontsize=8);self.map.tick_params(labelsize=8)
        self.map.set_title('London food-site experiment · simulated colony activity',loc='left',fontsize=11,pad=10)
        self.map.text(.012,.018,'Pale: unvisited food   ·   Green: visited at least once   ·   Gold: recent trail (fixed scale 0–15)\nTfL station coordinates · © OpenStreetMap contributors',
            transform=self.map.transAxes,color='#d2d9dc',fontsize=7,va='bottom',zorder=11,bbox={'fc':'#101c24','ec':'none','alpha':.8,'pad':4})
        for axis in (self.reached_plot,self.population_plot):
            axis.spines[['top','right']].set_visible(False);axis.tick_params(labelsize=7);axis.grid(alpha=.15,lw=.5);axis.set_xlabel('Simulation updates (not hours)',fontsize=8)
        self.reached_plot.set_ylabel('Food sites visited',fontsize=8);self.population_plot.set_ylabel('Live particles',fontsize=8)
        self.reached_line,=self.reached_plot.plot([],[],color='#158075',lw=1.3)
        self.population_line,=self.population_plot.plot([],[],color='#af7b16',lw=1.3)
        self.cursors=[axis.axvline(0,color='#555',lw=.8,ls='--') for axis in (self.reached_plot,self.population_plot)]
        self.reached_plot.set_ylim(0,len(foods)+1);self.population_plot.set_ylim(0,settings['max_agents']*1.03)
        self.reached_plot.set_xlim(0,settings['steps'])
        if run:self.set_frame(0)
        self.draw_idle()

    def set_frame(self,index):
        run=self.run_data
        if run is None:return
        self.image.set_data(run.trail[index])
        if self.show_agents:
            rgba=np.zeros((*run.occupied.shape[1:],4),dtype=np.float32);rgba[:,:,:3]=[1,.98,.83];rgba[:,:,3]=run.occupied[index]*.8
            self.agent_image.set_data(rgba);self.agent_image.set_visible(True)
        else:self.agent_image.set_visible(False)
        tick=int(run.stats[index,1]);visited=(run.contacts>=0)&(run.contacts<=tick)
        self.sites.set_facecolors(['#68bda7' if flag else '#f1eee0' for flag in visited])
        self.reached_line.set_data(run.steps[:index+1],run.stats[:index+1,3]);self.population_line.set_data(run.steps[:index+1],run.stats[:index+1,2])
        for cursor in self.cursors:cursor.set_xdata([tick,tick])
        self.draw_idle()

    def pick(self,event):
        if event.inaxes is not getattr(self,'map',None) or event.button!=1 or (self.toolbar and self.toolbar.mode):return
        distance=np.linalg.norm(self.map.transData.transform(self.xy)-[event.x,event.y],axis=1);index=int(distance.argmin())
        if distance[index]>14:return
        self.select_food(index);self.food_picked.emit(index)

    def select_food(self,index):
        self.selected=index;self.selection.set_offsets(self.xy[[index]])
        self.annotation.xy=self.xy[index];self.annotation.set_text(self.foods[index]['name']);self.annotation.set_visible(True);self.draw_idle()


class GrowthViewer(QMainWindow):
    def __init__(self,auto_run=True):
        super().__init__();self.setWindowTitle('Physarum — Growth laboratory');self.resize(1460,940);self.setMinimumSize(1120,760)
        self.scene=default_scene();self.run_data=None;self.worker=None;self.index=0;self.playing=False;self.playhead=0.;self.last_tick=time.monotonic();self.selected_food=None;self.previous_windows=[]
        self.closing=False
        self.build_ui();self.refresh_starts();self.preview()
        self.timer=QTimer(self);self.timer.setInterval(40);self.timer.timeout.connect(self.tick);self.timer.start()
        if auto_run:QTimer.singleShot(0,self.run)

    def build_ui(self):
        file=self.menuBar().addMenu('File');self.file_menu=file
        file.addAction('Open saved growth run…').triggered.connect(self.open_run)
        file.addAction('Save growth scenario…').triggered.connect(self.save_scenario)
        file.addAction('Open growth scenario…').triggered.connect(self.open_scenario)
        file.addSeparator();file.addAction('Open station-connection experiment').triggered.connect(self.open_network)
        file.addAction('Open four-node validation').triggered.connect(self.open_fixture)
        self.menuBar().addMenu('Help').addAction('The paper and this model…').triggered.connect(self.help)
        split=QSplitter(Qt.Orientation.Horizontal);left=QWidget();sidebar=QVBoxLayout(left);sidebar.setContentsMargins(16,14,16,14)
        heading=QLabel('GROWTH LABORATORY');heading.setStyleSheet('font-size: 17px; font-weight: 600;');sidebar.addWidget(heading)
        subtitle=QLabel('One starting patch. Station food sites.\nWatch local rules create a network.');subtitle.setWordWrap(True);sidebar.addWidget(subtitle)
        group=QGroupBox('Prepare the experiment');form=QFormLayout(group);form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.start=QComboBox();self.start.setMinimumContentsLength(17);self.start.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);form.addRow('Start at',self.start)
        self.choose=QPushButton('Choose station food sites…');self.choose.clicked.connect(self.choose_foods);form.addRow(self.choose)
        self.controls={}
        for key,label,low,high,step,decimals in [('seed','Random seed',0,2**31-1,1,0),('steps','Simulation updates',100,4000,100,0),
            ('food_strength','Food attraction',0,30,1,1),('division_interval','Divide every N updates',2,20,1,0),('river_aversion','Thames aversion',0,30,1,1)]:
            field=QDoubleSpinBox() if decimals else QSpinBox();field.setRange(low,high);field.setSingleStep(step)
            if decimals:field.setDecimals(decimals)
            field.setValue(DEFAULT_GROWTH[key]);field.valueChanged.connect(self.changed);self.controls[key]=field;form.addRow(label,field)
        self.controls['food_strength'].setToolTip('Strength of a synthetic food cue. Equal food sites are not passenger demand.')
        self.controls['division_interval'].setToolTip('A smaller interval permits faster population growth; this is not a measured biological division time.')
        self.controls['river_aversion'].setToolTip('Optional hypothetical repellent along the Thames; zero means the river is only a geographic guide.')
        self.start.currentIndexChanged.connect(self.changed);sidebar.addWidget(group)
        self.run_button=QPushButton('Compute growth experiment');self.run_button.clicked.connect(self.run);sidebar.addWidget(self.run_button)
        self.restore=QPushButton('Restore King’s Cross example');self.restore.clicked.connect(self.reset);sidebar.addWidget(self.restore)
        self.names=QCheckBox('Show all food-site names');self.names.toggled.connect(self.toggle_names);sidebar.addWidget(self.names)
        self.agents=QCheckBox('Show individual live particles');self.agents.toggled.connect(self.toggle_agents);sidebar.addWidget(self.agents)
        self.phase=QLabel();self.phase.setWordWrap(True);self.phase.setStyleSheet('font-size: 15px; font-weight: 600; margin-top: 12px;');sidebar.addWidget(self.phase)
        self.explanation=QLabel();self.explanation.setWordWrap(True);self.explanation.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);sidebar.addWidget(self.explanation)
        self.metrics=QLabel();self.metrics.setWordWrap(True);self.metrics.setStyleSheet('margin-top: 8px;');sidebar.addWidget(self.metrics)
        self.selected=QLabel('Click a food site for its name and first-contact time.');self.selected.setWordWrap(True);sidebar.addWidget(self.selected)
        note=QLabel('WHAT THE COLOURS MEAN\nGold is recent movement trail, not rail capacity.\nGreen means visited at least once, not still connected.\n\nThis is a particle growth model inspired by Physarum. London is a scaled experimental layout. Updates are not biological hours.');note.setWordWrap(True);note.setStyleSheet('margin-top: 12px;');sidebar.addWidget(note);sidebar.addStretch()
        scroll=QScrollArea();scroll.setWidget(left);scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame);scroll.setMinimumWidth(350);split.addWidget(scroll)
        right=QWidget();layout=QVBoxLayout(right);layout.setContentsMargins(4,12,12,8)
        self.run_label=QLabel();self.run_label.setWordWrap(True);layout.addWidget(self.run_label)
        self.canvas=GrowthFigure();self.canvas.food_picked.connect(self.pick_food)
        self.toolbar=NavigationToolbar2QT(self.canvas,self);layout.addWidget(self.toolbar);layout.addWidget(self.canvas,1)
        controls=QHBoxLayout();self.play_button=QPushButton('Play growth');self.play_button.clicked.connect(self.toggle_play);controls.addWidget(self.play_button)
        self.restart=QPushButton('Restart');self.restart.clicked.connect(lambda:self.scrub(0));controls.addWidget(self.restart)
        self.next_frame=QPushButton('Next recorded frame');self.next_frame.clicked.connect(lambda:self.scrub(self.index+1));controls.addWidget(self.next_frame)
        controls.addStretch();controls.addWidget(QLabel('Playback:'));self.speed=QComboBox()
        for value in (10,20,40,80,160):self.speed.addItem(f'{value} updates/s',value)
        self.speed.setCurrentIndex(2);controls.addWidget(self.speed);layout.addLayout(controls)
        self.timeline=QSlider(Qt.Orientation.Horizontal);self.timeline.valueChanged.connect(self.scrub);layout.addWidget(self.timeline)
        bottom=QHBoxLayout();bottom.addWidget(QLabel('Recorded frame:'));self.frame=QSpinBox();self.frame.valueChanged.connect(self.scrub);bottom.addWidget(self.frame)
        self.time_label=QLabel();bottom.addWidget(self.time_label);bottom.addStretch();layout.addLayout(bottom)
        split.addWidget(right);split.setSizes([350,1110]);self.setCentralWidget(split)

    def settings(self):
        settings=dict(getattr(self,'loaded_settings',DEFAULT_GROWTH));settings.update({key:field.value() for key,field in self.controls.items()});settings['start_id']=self.start.currentData();return settings
    def refresh_starts(self):
        old=self.start.currentData() or DEFAULT_GROWTH['start_id'];self.start.blockSignals(True);self.start.clear()
        for node in self.scene['nodes']:
            if node['kind']=='station':self.start.addItem(node['name'],node['key'])
        index=self.start.findData(old);self.start.setCurrentIndex(max(0,index));self.start.blockSignals(False)
    def changed(self):
        if self.run_data:self.statusBar().showMessage('Controls describe the next experiment. Display still shows the saved run; compute again to apply changes.')
    def preview(self):
        self.pause();self.run_data=None;self.selected_food=None;self.selected.setText('Click a food site for its name.');self.canvas.setup(self.scene,self.settings());self.toolbar.update()
        self.run_label.setText('SCENARIO PREVIEW · no growth states computed');self.phase.setText('Ready to inoculate')
        self.explanation.setText('The starting station gets a small patch of simulated material. Each other station is a food attractor. Compute an experiment, then press Play growth.')
        self.metrics.setText(f'{sum(n["kind"]=="station" for n in self.scene["nodes"])} equal station food sites · 1 initial patch')
        for widget in (self.play_button,self.timeline,self.frame,self.restart,self.next_frame):widget.setEnabled(False)
        self.time_label.setText('No computed state')
    def busy(self,value):
        for widget in (self.run_button,self.choose,self.restore,self.start,self.file_menu,*self.controls.values()):widget.setEnabled(not value)
    def run(self):
        if self.worker and self.worker.isRunning():return
        try:prepare_growth(self.scene,self.settings())
        except Exception as error:QMessageBox.warning(self,'Invalid growth scenario',str(error));return
        self.pause();self.busy(True);self.statusBar().showMessage('Computing the C++ particle experiment and saving its fields…')
        self.worker=GrowthWorker(self.scene,self.settings(),self);self.worker.completed.connect(self.set_run);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.finished);self.worker.start()
    def finished(self):
        self.busy(False)
        if self.closing:QTimer.singleShot(0,self.close)
    def failed(self,message):
        if not self.worker.cancel.is_set():QMessageBox.warning(self,'Growth experiment failed',message)
        self.statusBar().showMessage('Experiment stopped; its inputs and any partial results are retained.')
    def set_run(self,run):
        self.pause();self.scene=copy.deepcopy(run.scene);self.loaded_settings=dict(run.settings);self.run_data=run;self.index=0;self.playhead=0.;self.selected_food=None
        self.selected.setText('Click a food site for its name and first-contact time.')
        self.refresh_starts();self.start.setCurrentIndex(self.start.findData(run.settings['start_id']))
        for key,field in self.controls.items():field.blockSignals(True);field.setValue(run.settings[key]);field.blockSignals(False)
        self.canvas.setup(self.scene,run.settings,run);self.toolbar.update();self.frame.setRange(0,len(run.stats)-1);self.timeline.setRange(0,len(run.stats)-1)
        for widget in (self.play_button,self.timeline,self.frame,self.restart,self.next_frame):widget.setEnabled(True)
        start=next(n['name'] for n in run.foods if n['key']==run.settings['start_id'])
        self.run_label.setText(f'RECORDED C++ GROWTH · start: {start} · {len(run.foods)} food sites · seed {run.settings["seed"]} · fixed trail colour scale')
        try:location=run.folder.relative_to(ROOT)
        except ValueError:location=run.folder
        self.statusBar().showMessage(f'Automatically saved: {location}');self.display_frame(0)
    def display_frame(self,index):
        run=self.run_data
        if run is None:return
        self.index=max(0,min(int(index),len(run.stats)-1));i=self.index;self.canvas.set_frame(i)
        for control in (self.timeline,self.frame):control.blockSignals(True);control.setValue(i);control.blockSignals(False)
        title,explanation=explain_growth(run,i);self.phase.setText(title);self.explanation.setText(explanation)
        self.metrics.setText(f'Visited at least once: {int(run.stats[i,3])} / {len(run.foods)}\nLive particles: {int(run.stats[i,2]):,}\nBirths: {int(run.stats[i,6]):,} · removals: {int(run.stats[i,7]):,}')
        self.time_label.setText(f'Update {int(run.stats[i,1])} / {run.settings["steps"]} · saved every {run.settings["frame_every"]} updates')
        if self.selected_food is not None:self.update_selected()
    def pick_food(self,index):self.selected_food=index;self.canvas.select_food(index);self.update_selected()
    def update_selected(self):
        run=self.run_data;index=self.selected_food
        if run is None or index is None:return
        contact=run.contacts[index];tick=int(run.stats[self.index,1])
        state='not yet visited' if contact<0 or contact>tick else f'first visited at update {contact}'
        self.selected.setText(run.foods[index]['name']+'\n'+state+'. A visit does not establish a permanent connection.')
    def pause(self):self.playing=False;self.play_button.setText('Play growth')
    def toggle_play(self):
        if self.run_data is None:return
        if self.playing:self.pause();return
        if self.index==len(self.run_data.stats)-1:self.display_frame(0)
        self.playhead=float(self.run_data.stats[self.index,1]);self.last_tick=time.monotonic();self.playing=True;self.play_button.setText('Pause')
    def scrub(self,index):self.pause();self.display_frame(index)
    def tick(self):
        now=time.monotonic();elapsed=min(.25,now-self.last_tick);self.last_tick=now
        if not self.playing or self.run_data is None:return
        self.playhead=min(self.run_data.settings['steps'],self.playhead+elapsed*self.speed.currentData())
        index=min(len(self.run_data.stats)-1,int(self.playhead/self.run_data.settings['frame_every']))
        if index!=self.index:self.display_frame(index)
        if index==len(self.run_data.stats)-1:self.pause()
    def choose_foods(self):
        dialog=StationDialog(self.scene['geography'],{n['tfl_id'] for n in self.scene['nodes'] if n['kind']=='station'},self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        keys=dialog.selected()
        if not 3<=len(keys)<=80:QMessageBox.warning(self,'Food count','Choose 3–80 food sites.');return
        lookup={n['tfl_id']:n for n in self.scene['geography']['station_catalog']};nodes=[]
        for key in keys:node=copy.deepcopy(lookup[key]);node['key']=key;nodes.append(node)
        candidate={**self.scene,'nodes':nodes};old_scene=self.scene;self.scene=candidate;self.refresh_starts()
        try:prepare_growth(self.scene,self.settings());self.preview()
        except Exception as error:self.scene=old_scene;self.refresh_starts();QMessageBox.warning(self,'Invalid food layout',str(error))
    def reset(self):
        self.scene=default_scene();self.loaded_settings=dict(DEFAULT_GROWTH);self.refresh_starts();self.start.setCurrentIndex(self.start.findData(DEFAULT_GROWTH['start_id']))
        for key,control in self.controls.items():control.setValue(DEFAULT_GROWTH[key])
        self.preview()
    def toggle_names(self,value):
        self.canvas.show_names=value
        for label in getattr(self.canvas,'names',[]):label.set_visible(value)
        self.canvas.draw_idle()
    def toggle_agents(self,value):
        self.canvas.show_agents=value
        if self.run_data:self.canvas.set_frame(self.index)
    def open_run(self):
        folder=QFileDialog.getExistingDirectory(self,'Open recorded growth run',str(ROOT/'results/growth_runs'))
        if folder:
            try:self.set_run(load_growth_run(folder))
            except Exception as error:QMessageBox.warning(self,'Invalid growth run',str(error))
    def save_scenario(self):
        path,_=QFileDialog.getSaveFileName(self,'Save growth scenario','london-growth.json','Growth scenario (*.json)')
        if path:Path(path).write_text(json.dumps(dict(scene=self.scene,settings=self.settings()),indent=2,ensure_ascii=False)+'\n')
    def open_scenario(self):
        path,_=QFileDialog.getOpenFileName(self,'Open growth scenario','','Growth scenario (*.json)')
        if not path:return
        try:
            data=json.loads(Path(path).read_text());prepare_growth(data['scene'],data['settings'])
            self.scene=data['scene'];self.loaded_settings=data['settings'];self.refresh_starts();self.start.setCurrentIndex(self.start.findData(data['settings']['start_id']))
            for key,field in self.controls.items():field.setValue(data['settings'][key])
            self.preview()
        except Exception as error:QMessageBox.warning(self,'Invalid growth scenario',str(error))
    def open_network(self):
        window=SpatialViewer();window.show();self.previous_windows.append(window)
    def open_fixture(self):
        window=Viewer();window.show();self.previous_windows.append(window)
    def help(self):
        QMessageBox.information(self,'The experiment and the model',
            'Tero et al. (2010), Fig. 1: a living Physarum inoculum grew from Tokyo toward food sites. Their numerical model in Fig. 4 instead began with an existing fine mesh.\n\n'
            'This separate mode uses a Jones-inspired chemotactic particle model to explore outward growth. Each particle senses three directions, moves toward stronger cues and deposits trail. Sparse moving regions can divide; crowded regions lose particles.\n\n'
            'Implementation choices include a local seed disk, smooth Gaussian food cues, weaker cues after first contact, reflecting boundaries and the growth/population settings. These are recorded, not a claim of exact paper replication.\n\n'
            'Gold shows recent trail activity on a fixed 0–15 signal scale; optional bright specks show live particles. This is not the conductivity or flow from the existing Tero solver. Food markers mean visited at least once, not a verified connected railway.\n\n'
            'Station positions and the Thames come from the frozen geographic data. Food strength is synthetic. Thames aversion is an optional assumed repellent; surface elevation does not affect this model. No train curvature radius, capacity or ground engineering is modelled.\n\n'
            'Every run saves inputs, raw fields, contact events, counters, checksums and source/binary hashes. The animation replays those computed snapshots. See docs/GROWTH_EXPERIMENT.md for the complete protocol.')
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.closing=True;self.pause();self.worker.cancel.set();self.statusBar().showMessage('Cancelling the growth calculation…');event.ignore();return
        self.timer.stop()
        event.accept()
