"""London and local sandbox editor. Design edits never change a recorded run."""
import copy
import numpy as np
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle
from matplotlib.widgets import RectangleSelector
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
from PySide6.QtCore import Signal,Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QCheckBox,QPushButton,QComboBox,QCompleter,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QSplitter,QTabWidget)
try:
    from .spatial_data import within_coverage,is_food
    from .scene_design import is_sandbox,scene_title,scene_credit,design_bounds,food_nodes,SANDBOX_EXAMPLES
    from .mesh_data import prepare_mesh_experiment
    from .map_labels import FoodLabels
except ImportError:
    from spatial_data import within_coverage,is_food
    from scene_design import is_sandbox,scene_title,scene_credit,design_bounds,food_nodes,SANDBOX_EXAMPLES
    from mesh_data import prepare_mesh_experiment
    from map_labels import FoodLabels

class LayoutCanvas(FigureCanvasQTAgg):
    station_clicked=Signal(str);restriction_drawn=Signal(object);food_added=Signal(float,float);food_selected=Signal(str);food_moved=Signal(str,float,float);food_removed=Signal(str);barrier_selected=Signal(int)
    def __init__(self):
        self.figure=Figure(figsize=(11,7),dpi=100,layout='compressed',facecolor='white');super().__init__(self.figure)
        self.axis=None;self.scene=None;self.selector=None;self.drawing=False;self.names=True;self.elevation=False;self.mode='select';self.labels=None;self.drag_key=None;self.selected_key=None;self.selected_barrier=None;self.preview_mesh=None
        self.mpl_connect('button_press_event',self.click);self.mpl_connect('motion_notify_event',self.motion);self.mpl_connect('button_release_event',self.release)
    def setup(self,scene,reset=False):
        limits=(self.axis.get_xlim(),self.axis.get_ylim()) if self.axis is not None and not reset else None
        if self.selector:self.selector.disconnect_events()
        if self.labels:self.labels.disconnect()
        self.scene=scene;self.figure.clear();self.axis=self.figure.add_subplot();axis=self.axis;axis.set_facecolor('#fafbf8')
        self.catalog=[n for n in scene['geography']['station_catalog'] if within_coverage(n,scene['geography'])];self.xy=np.array([[n['x'],n['y']] for n in self.catalog]).reshape(-1,2)
        keys={n['key'] for n in scene['nodes'] if n['kind']=='station'};self.selected=np.array([n['tfl_id'] in keys for n in self.catalog],dtype=bool)
        if self.elevation and not is_sandbox(scene):
            e=scene['geography']['elevation'];axis.pcolormesh(e['x'],e['y'],e['metres'],shading='auto',cmap='gist_earth',alpha=.22,zorder=0)
        axis.add_collection(LineCollection([way['xy_km'] for way in scene['geography']['river']],colors='#83b3c4',linewidths=1.6,zorder=1))
        if self.preview_mesh:
            mesh=self.preview_mesh;xy=np.array([[n['x'],n['y']] for n in mesh['nodes']]);edges=np.array([[e['from'],e['to']] for e in mesh['edges']])
            axis.add_collection(LineCollection(xy[edges],colors='#8aa297',linewidths=.35,alpha=.55,zorder=1))
        if len(self.xy):axis.scatter(*self.xy[~self.selected].T,s=15,facecolors='#e3e8e1',edgecolors='#94a297',linewidths=.5,zorder=2)
        self.foods=food_nodes(scene);self.food_xy=np.array([[n['x'],n['y']] for n in self.foods]).reshape(-1,2)
        for kind,marker,color in [('station','o','#13856e'),('food','D','#b17c2b')]:
            indices=[i for i,n in enumerate(self.foods) if n['kind']==kind]
            if indices:axis.scatter(*self.food_xy[indices].T,s=38,marker=marker,facecolors='#fafbf8',edgecolors=color,linewidths=1.25,zorder=5)
        for i,(x0,y0,x1,y1) in enumerate(scene['barriers']):
            axis.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor='#c89686',edgecolor='#a76351',hatch='//',alpha=.35,zorder=2))
            axis.text((x0+x1)/2,(y0+y1)/2,f'B{i+1}',ha='center',va='center',fontsize=8,color='#794b3b',zorder=3)
        self.barrier_highlight=Rectangle((0,0),0,0,fill=False,edgecolor='#a44d35',linewidth=2,zorder=9,visible=False);axis.add_patch(self.barrier_highlight);self.focus_barrier(self.selected_barrier)
        self.labels=FoodLabels(axis,self.foods,'all' if self.names else 'none')
        axis.set_aspect('equal');axis.set_xlabel('Local easting (km)' if is_sandbox(scene) else 'British National Grid easting (km)',fontsize=9);axis.set_ylabel('Northing (km)',fontsize=9);axis.tick_params(labelsize=8);axis.spines[['top','right']].set_visible(False)
        if limits:axis.set_xlim(*limits[0]);axis.set_ylim(*limits[1])
        else:
            x0,y0,x1,y1=design_bounds(scene);axis.set_xlim(x0,x1);axis.set_ylim(y0,y1)
        axis.set_title(f"{scene_title(scene)} design · {len(self.foods)} food sites · {len(scene['barriers'])} blocked areas",loc='left',fontsize=12,pad=13)
        axis.text(.01,.01,scene_credit(scene),transform=axis.transAxes,fontsize=7,color='#40514b',bbox=dict(facecolor='white',alpha=.9,edgecolor='none'),zorder=8)
        self.annotation=axis.annotate('',xy=(0,0),xytext=(9,12),textcoords='offset points',fontsize=9,bbox=dict(facecolor='white',edgecolor='#b8c4b8',alpha=.97),zorder=12,visible=False);self.annotation.set_in_layout(False)
        self.highlight=axis.plot([],[],'o',ms=13,mfc='none',mec='#d38b2e',mew=1.5,zorder=9)[0];self.drag_marker=axis.plot([],[],'D',ms=8,color='#b17c2b',zorder=10)[0]
        self.selector=RectangleSelector(axis,self.rectangle,useblit=False,button=[1],minspanx=.05,minspany=.05,spancoords='data',interactive=False);self.selector.set_active(self.drawing);self.focus(self.selected_key);self.draw_idle()
    def nearest(self,event,xy):
        if event.inaxes!=self.axis or not len(xy):return None
        distance=np.linalg.norm(self.axis.transData.transform(xy)-[event.x,event.y],axis=1);i=int(distance.argmin());return i if distance[i]<=12 else None
    def click(self,event):
        if self.scene is None or self.drawing or event.button!=1 or event.inaxes!=self.axis or (self.toolbar and self.toolbar.mode):return
        if self.mode=='add':
            if not event.dblclick:self.food_added.emit(event.xdata,event.ydata)
            return
        i=self.nearest(event,self.food_xy)
        if i is not None:
            node=self.foods[i]
            if self.mode=='delete':self.food_removed.emit(node['key']);return
            self.food_selected.emit(node['key']);self.focus(node['key'])
            if self.mode=='move' and node['kind']=='food':self.drag_key=node['key']
            return
        if self.mode=='select':
            for j,(x0,y0,x1,y1) in reversed(list(enumerate(self.scene['barriers']))):
                if x0<=event.xdata<=x1 and y0<=event.ydata<=y1:self.barrier_selected.emit(j);return
            i=self.nearest(event,self.xy)
            if i is not None:self.station_clicked.emit(self.catalog[i]['tfl_id'])
    def motion(self,event):
        if self.scene is None or event.inaxes!=self.axis:return
        if self.drag_key:
            self.drag_marker.set_data([event.xdata],[event.ydata]);self.draw_idle();return
        if self.drawing:return
        i=self.nearest(event,self.food_xy);node=self.foods[i] if i is not None else None
        if node is None:
            i=self.nearest(event,self.xy);node=self.catalog[i] if i is not None else None
        if node:
            self.annotation.xy=(node['x'],node['y']);role='Your food site · select, rename or move' if node['kind']=='food' else 'TfL station · click to select/add';self.annotation.set_text(node['name']+'\n'+role);self.annotation.set_visible(True);self.draw_idle()
        elif self.annotation.get_visible():self.annotation.set_visible(False);self.draw_idle()
    def release(self,event):
        if not self.drag_key:return
        key=self.drag_key;self.drag_key=None;self.drag_marker.set_data([],[])
        if event.inaxes==self.axis and event.xdata is not None and not (self.toolbar and self.toolbar.mode):self.food_moved.emit(key,event.xdata,event.ydata)
        self.draw_idle()
    def focus(self,key):
        self.selected_key=key
        if self.scene is None:return
        node=next((n for n in self.foods if n['key']==key),None);self.highlight.set_data([node['x']],[node['y']]) if node else self.highlight.set_data([],[]);self.draw_idle()
    def focus_barrier(self,index):
        self.selected_barrier=index
        if index is not None and 0<=index<len(self.scene['barriers']):
            x0,y0,x1,y1=self.scene['barriers'][index];self.barrier_highlight.set_bounds(x0,y0,x1-x0,y1-y0);self.barrier_highlight.set_visible(True)
        else:self.barrier_highlight.set_visible(False)
        self.draw_idle()
    def rectangle(self,start,end):
        if self.drawing and all(v is not None for v in (start.xdata,start.ydata,end.xdata,end.ydata)):self.restriction_drawn.emit([min(start.xdata,end.xdata),min(start.ydata,end.ydata),max(start.xdata,end.xdata),max(start.ydata,end.ydata)])
    def set_drawing(self,value):
        if value:self.exit_navigation()
        self.drawing=value
        if self.selector:self.selector.set_active(value)
    def exit_navigation(self):
        if self.toolbar and self.toolbar.mode:
            self.toolbar.pan() if 'pan' in str(self.toolbar.mode).lower() else self.toolbar.zoom()

class LayoutPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.selected_key=None;self.rebuilding=False;self.prepared=None;self.preview_signature=None;layout=QVBoxLayout(self)
        self.instruction=QLabel('Design your experiment here. Add stations or place your own food. Changes apply when you compute; the Network tab keeps its saved result.');self.instruction.setWordWrap(True);layout.addWidget(self.instruction)
        stations=QHBoxLayout();self.station=QComboBox();self.station.setEditable(True);self.station.setMinimumContentsLength(24);self.station.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.station.setInsertPolicy(QComboBox.InsertPolicy.NoInsert);stations.addWidget(self.station,1);self.add_station_button=QPushButton('Use station');self.add_station_button.clicked.connect(self.use_station);stations.addWidget(self.add_station_button)
        self.examples=QComboBox()
        for key,(name,description,task) in SANDBOX_EXAMPLES.items():self.examples.addItem(name,key);self.examples.setItemData(self.examples.count()-1,description,Qt.ItemDataRole.ToolTipRole)
        stations.addWidget(self.examples,1);self.example=QPushButton('Load example');self.example.setToolTip('Replaces the current design and restores default model controls. Geometry edits can be undone.');self.example.clicked.connect(lambda:owner.load_example(self.examples.currentData()));stations.addWidget(self.example);layout.addLayout(stations)
        bar=QHBoxLayout();self.tools=QComboBox()
        for label,key in [('Select / inspect','select'),('Place food · click map','add'),('Move custom food · drag','move'),('Remove food · click','delete')]:self.tools.addItem(label,key)
        bar.addWidget(self.tools);self.draw_button=QPushButton('Draw blocked area');self.draw_button.setCheckable(True);bar.addWidget(self.draw_button);self.undo_button=QPushButton('Undo');self.redo_button=QPushButton('Redo');bar.addWidget(self.undo_button);bar.addWidget(self.redo_button)
        clear=QPushButton('Clear food');clear.clicked.connect(owner.clear_foods);bar.addWidget(clear);self.details=QPushButton('Edit coordinates');self.details.setCheckable(True);bar.addWidget(self.details);reset=QPushButton('Fit map');bar.addWidget(reset);layout.addLayout(bar)
        row=QHBoxLayout();names=QCheckBox('Site names');names.setChecked(True);terrain=QCheckBox('Surface elevation');self.terrain=terrain;row.addWidget(names);row.addWidget(terrain);row.addWidget(QLabel('○ Real station   ◇ Your food   ▧ Blocked area'));row.addStretch();layout.addLayout(row)
        preview_row=QHBoxLayout();self.preview_button=QPushButton('Check design / preview paths');self.preview_button.clicked.connect(self.preview_paths);preview_row.addWidget(self.preview_button);self.preview_visible=QCheckBox('Show candidate paths');self.preview_visible.setChecked(True);self.preview_visible.setEnabled(False);self.preview_visible.toggled.connect(self.render_preview);preview_row.addWidget(self.preview_visible);preview_row.addStretch();layout.addLayout(preview_row)
        self.preview_status=QLabel('Preview checks the geometry and recording size without running the flow solver.');self.preview_status.setWordWrap(True);layout.addWidget(self.preview_status)
        split=QSplitter(Qt.Orientation.Vertical);layout.addWidget(split,1);view=QWidget();vl=QVBoxLayout(view);vl.setContentsMargins(0,0,0,0);self.canvas=LayoutCanvas();vl.addWidget(NavigationToolbar2QT(self.canvas,self));vl.addWidget(self.canvas,1);split.addWidget(view)
        self.tables=QTabWidget();self.tables.setMinimumHeight(80);self.tables.setMaximumHeight(180);split.addWidget(self.tables);self.details.toggled.connect(self.tables.setVisible);self.tables.setVisible(False)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Food / station name','Type','Easting km','Northing km']);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);self.tables.addTab(self.table,'Food sites')
        blocked=QWidget();bl=QVBoxLayout(blocked);bl.setContentsMargins(0,0,0,0);self.barrier_table=QTableWidget(0,4);self.barrier_table.setHorizontalHeaderLabels(['Min easting km','Min northing km','Max easting km','Max northing km']);self.barrier_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.barrier_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);bl.addWidget(self.barrier_table,1);self.remove_block=QPushButton('Remove selected blocked area');self.remove_block.clicked.connect(lambda:owner.remove_barrier(self.barrier_table.currentRow()));bl.addWidget(self.remove_block);self.tables.addTab(blocked,'Blocked areas');split.setSizes([550,170])
        self.canvas.station_clicked.connect(owner.add_station);self.canvas.food_added.connect(owner.add_food);self.canvas.food_moved.connect(owner.move_food);self.canvas.food_removed.connect(owner.remove_food);self.canvas.food_selected.connect(self.select_food);self.canvas.restriction_drawn.connect(owner.add_restriction)
        self.canvas.barrier_selected.connect(self.select_barrier);self.barrier_table.itemChanged.connect(self.barrier_changed);self.barrier_table.itemSelectionChanged.connect(self.barrier_selection)
        self.tools.currentIndexChanged.connect(self.tool_changed);self.tools.activated.connect(self.tool_changed);self.draw_button.toggled.connect(self.drawing_changed);self.undo_button.clicked.connect(owner.undo_design);self.redo_button.clicked.connect(owner.redo_design);names.toggled.connect(lambda value:self.overlay('names',value));terrain.toggled.connect(lambda value:self.overlay('elevation',value));reset.clicked.connect(lambda:self.canvas.setup(owner.scene,True));self.table.itemChanged.connect(self.cell_changed);self.table.itemSelectionChanged.connect(self.table_selected)
    def drawing_changed(self,value):
        self.canvas.set_drawing(value)
        if value:self.instruction.setText('Drag a rectangle to block candidate paths. Food must stay outside it. Edit its bounds in Blocked areas below.')
        else:self.tool_changed()
    def tool_changed(self):
        self.canvas.exit_navigation();self.draw_button.setChecked(False);self.canvas.mode=self.tools.currentData();text={'select':'Click an existing point to inspect it; click a grey London station to add it.','add':'Click empty space to place food. Rename it in the table below.','move':'Drag your diamond-shaped food sites. Official stations keep their real coordinates.','delete':'Click a site to remove it. Undo restores it.'}[self.canvas.mode];self.instruction.setText(text)
    def use_station(self):
        if self.station.currentData() and self.station.currentText()==self.station.itemText(self.station.currentIndex()):self.owner.add_station(self.station.currentData())
        else:self.owner.statusBar().showMessage('Choose a station from the search suggestions, then Use station.')
    def overlay(self,key,value):setattr(self.canvas,key,value);self.canvas.setup(self.owner.scene)
    def refresh(self,reset=False):
        scene=self.owner.scene
        if self.preview_signature is not None and self.preview_signature!=(scene,self.owner.settings()):
            self.prepared=None;self.preview_signature=None;self.preview_status.setText('Design or controls changed. Check design again to refresh candidate paths and size.');self.preview_status.setStyleSheet('')
        self.canvas.preview_mesh=self.prepared['mesh'] if self.prepared and self.preview_visible.isChecked() else None;self.preview_visible.setEnabled(self.prepared is not None);self.preview_button.setEnabled(len(food_nodes(scene))>=2)
        self.canvas.setup(scene,reset);self.rebuilding=True;foods=food_nodes(scene);self.table.setRowCount(len(foods))
        for i,n in enumerate(foods):
            for j,text in enumerate((n['name'],'TfL station' if n['kind']=='station' else 'Your food',f"{n['x']:.4f}",f"{n['y']:.4f}")):
                item=QTableWidgetItem(text);item.setData(Qt.ItemDataRole.UserRole,n['key'])
                if n['kind']!='food' or j==1:item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i,j,item)
        self.barrier_table.setRowCount(len(scene['barriers']))
        for i,rect in enumerate(scene['barriers']):
            self.barrier_table.setVerticalHeaderItem(i,QTableWidgetItem(f'B{i+1}'))
            for j,value in enumerate(rect):self.barrier_table.setItem(i,j,QTableWidgetItem(f'{value:.4f}'))
        self.remove_block.setEnabled(bool(scene['barriers']));self.rebuilding=False;catalog=[n for n in scene['geography']['station_catalog'] if within_coverage(n,scene['geography'])];catalog_keys=tuple(n['tfl_id'] for n in catalog)
        if getattr(self,'catalog_keys',None)!=catalog_keys:
            self.catalog_keys=catalog_keys;self.station.clear();self.station.addItem('Search for a London station…',None)
            for n in sorted(catalog,key=lambda n:n['name']):self.station.addItem(n['name'],n['tfl_id'])
            self.station.completer().setFilterMode(Qt.MatchFlag.MatchContains);self.station.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.station.setVisible(not is_sandbox(scene));self.add_station_button.setVisible(not is_sandbox(scene));self.example.setVisible(is_sandbox(scene));self.examples.setVisible(is_sandbox(scene));self.terrain.setEnabled(not is_sandbox(scene));self.undo_button.setEnabled(bool(self.owner.design_history.undo_stack));self.redo_button.setEnabled(bool(self.owner.design_history.redo_stack))
    def select_food(self,key):
        self.selected_key=key;self.canvas.focus_barrier(None);self.canvas.focus(key);self.details.setChecked(True);self.tables.setCurrentIndex(0)
        for i in range(self.table.rowCount()):
            if self.table.item(i,0).data(Qt.ItemDataRole.UserRole)==key:self.table.selectRow(i);break
    def table_selected(self):
        if self.rebuilding:return
        row=self.table.currentRow()
        if row>=0 and self.table.item(row,0):self.selected_key=self.table.item(row,0).data(Qt.ItemDataRole.UserRole);self.canvas.focus_barrier(None);self.canvas.focus(self.selected_key)
    def cell_changed(self,item):
        if self.rebuilding:return
        key=item.data(Qt.ItemDataRole.UserRole)
        try:
            if item.column()==0:self.owner.rename_food(key,item.text())
            elif item.column() in (2,3):
                row=item.row();self.owner.move_food(key,float(self.table.item(row,2).text()),float(self.table.item(row,3).text()))
        except ValueError as error:self.owner.statusBar().showMessage(str(error));self.refresh()
    def select_barrier(self,index):
        self.canvas.focus(None);self.canvas.focus_barrier(index);self.details.setChecked(True);self.tables.setCurrentIndex(1);self.barrier_table.selectRow(index)
    def barrier_selection(self):
        if not self.rebuilding and self.barrier_table.currentRow()>=0:self.canvas.focus(None);self.canvas.focus_barrier(self.barrier_table.currentRow())
    def barrier_changed(self,item):
        if self.rebuilding:return
        try:self.owner.set_barrier(item.row(),[float(self.barrier_table.item(item.row(),j).text()) for j in range(4)])
        except ValueError as error:self.owner.statusBar().showMessage(str(error));self.refresh()
    def preview_paths(self):
        self.preview_signature=(copy.deepcopy(self.owner.scene),copy.deepcopy(self.owner.settings()))
        try:
            self.prepared=prepare_mesh_experiment(self.owner.scene,self.owner.settings());p=self.prepared;m=p['mesh']
            self.preview_status.setStyleSheet('color:#287c66;');self.preview_status.setText(f"READY · All {m['food_count']} foods connected in candidate mesh · {len(m['nodes']):,} vertices · {len(m['edges']):,} segments · {p['states']:,} states · {p['raw_bytes']/1e6:.1f} MB raw data. Geometry preview only; retained connectivity is measured after computing.")
            self.preview_visible.setChecked(True);self.preview_visible.setEnabled(True)
        except (ValueError,KeyError,TypeError) as error:
            self.prepared=None;self.preview_visible.setEnabled(False);self.preview_status.setStyleSheet('color:#a44d35;');self.preview_status.setText('CHECK DESIGN · '+str(error))
        self.render_preview()
    def render_preview(self,*_):
        self.canvas.preview_mesh=self.prepared['mesh'] if self.prepared and self.preview_visible.isChecked() else None;self.canvas.setup(self.owner.scene)
