"""Matched-scale final-state maps and explicit comparison conditions."""
from pathlib import Path
import textwrap
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QFileDialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
import numpy as np
try:
    from .experiment_comparison import comparison_data,export_comparison
    from .mesh_plot import draw_tubes
    from .scene_design import scene_credit
except ImportError:
    from experiment_comparison import comparison_data,export_comparison
    from mesh_plot import draw_tubes
    from scene_design import scene_credit


class ComparisonPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.key=None;self.data=None;self.runs=None;layout=QVBoxLayout(self)
        bar=QHBoxLayout();self.pin=QPushButton('Keep current as reference');self.pin.clicked.connect(lambda:owner.pin_reference(owner.run_data));bar.addWidget(self.pin);choose=QPushButton('Choose reference from library');choose.clicked.connect(lambda:owner.tabs.setCurrentWidget(owner.library));bar.addWidget(choose);automatic=QPushButton('Use previous run automatically');automatic.clicked.connect(owner.automatic_reference);bar.addWidget(automatic);self.export_button=QPushButton('Export comparison…');self.export_button.clicked.connect(self.export);bar.addWidget(self.export_button);layout.addLayout(bar)
        self.status=QLabel('Choose a saved reference, or compute a second experiment to compare final networks.');self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        self.conditions=QLabel('');self.conditions.setWordWrap(True);self.conditions.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.conditions)
        self.figure=Figure(figsize=(12,5),dpi=100,layout='constrained',facecolor='white');self.figure.get_layout_engine().set(rect=(0,.06,1,.94));self.canvas=FigureCanvasQTAgg(self.figure);layout.addWidget(NavigationToolbar2QT(self.canvas,self));layout.addWidget(self.canvas,1)
        self.table=QTableWidget(0,4);self.table.setMaximumHeight(180);self.table.setHorizontalHeaderLabels(['Measurement','Reference','Current','Current − reference']);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(self.table)
        self.changes=QLabel('');self.changes.setWordWrap(True);self.changes.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.changes);self.export_button.setEnabled(False)
    def update_runs(self,a,b,cutoff):
        self.pin.setEnabled(b is not None)
        if a is None or b is None:
            self.data=None;self.key=None;self.runs=None;self.export_button.setEnabled(False);self.table.setRowCount(0);self.status.setText('Choose a saved reference, or compute a second experiment to compare final networks.');self.conditions.clear();self.changes.clear()
            for axis in self.figure.axes:
                if hasattr(axis,'_food_labels'):axis._food_labels.disconnect()
            self.figure.clear();self.canvas.draw_idle();return
        titles=tuple(self.owner.run_title(r) for r in (a,b));key=(id(a),id(b),cutoff,titles,self.owner.reference_pinned)
        if key==self.key:return
        data=self.data if self.key and self.key[:3]==key[:3] else comparison_data(a,b,cutoff);self.data=data;self.key=key;self.runs=(a,b);self.export_button.setEnabled(True)
        self.status.setText(('REFERENCE PINNED · ' if self.owner.reference_pinned else 'PREVIOUS RUN REFERENCE · ')+f'Final states · D ≥ {cutoff:g}\n'+data['summary'])
        labels={'same_coordinate_context':'coordinate context','same_food_sites':'food sites','same_candidate_geometry':'candidate geometry','same_initial_conductivities':'initial D','same_food_pair_schedule':'food-pair schedule','same_injected_current':'injected flow'}
        self.conditions.setText('MATCH CHECKS · '+'   |   '.join(f"{label}: {'same' if data['conditions'][k] else 'different'}" for k,label in labels.items()))
        for axis in self.figure.axes:
            if hasattr(axis,'_food_labels'):axis._food_labels.disconnect()
        self.figure.clear();shared=data['conditions']['same_coordinate_context'];axes=self.figure.subplots(1,2,sharex=shared,sharey=shared)
        for axis,run,role,title in zip(axes,(a,b),('Reference','Current'),titles):
            draw_tubes(axis,run,len(run.times)-1,cutoff,True);axis.set_title(f'{role} · '+textwrap.fill(title,40)+f'\nt = {run.times[-1]:g}',loc='left',fontsize=9,parse_math=False)
        if data['conditions']['same_coordinate_context']:
            xy=np.array([[n['x'],n['y']] for r in (a,b) for n in r.mesh['nodes']]);lo=xy.min(axis=0)-.2;hi=xy.max(axis=0)+.2
            for axis in axes:axis.set_xlim(lo[0],hi[0]);axis.set_ylim(lo[1],hi[1])
        credit=' · '.join(dict.fromkeys(scene_credit(r.scene) for r in (a,b)))
        self.figure.text(.01,.005,f'{credit}\nD ≥ {cutoff:g}; fixed width ∝ D¼. Blue/orange dots: imposed source/sink. Final states; model time, not biological hours.',fontsize=7,color='#59665e')
        self.canvas.draw_idle();self.table.setRowCount(len(data['measurements']))
        def fmt(v):return 'Unavailable' if v is None else f'{v:.5g}'
        for i,row in enumerate(data['measurements']):
            for j,text in enumerate((f"{row['label']} ({row['unit']})",fmt(row['reference']),fmt(row['current']),fmt(row['delta']))):self.table.setItem(i,j,QTableWidgetItem(text))
        def short(value):
            text=str(value);return text if len(text)<=85 else text[:82]+'…'
        changed='; '.join(f"{row['label']}: {short(row['reference'])} → {short(row['current'])}" for row in data['changes'][:4]) or 'No recorded model controls changed.'
        if len(data['changes'])>4:changed+=f'; {len(data["changes"])-4} further changes are included in the exported record.'
        numerical=data['numerical'];numerical_text=f"\nMatched integration trajectories · maximum |ΔD| {numerical['max_D_difference']:.6g}; final {numerical['final_D_max_difference']:.6g}. Finite differences, not errors against an exact solution." if numerical else ''
        self.changes.setText('CHANGED CONTROLS · '+changed+numerical_text+'\nDeltas describe differences, not improvement scores. Repeat across seeds, mesh spacing and cutoffs before stronger conclusions.')
    def export(self):
        if not self.runs:return
        folder=QFileDialog.getExistingDirectory(self,'Export comparison figures and measurements',str(self.owner.run_data.folder))
        if not folder:return
        try:
            a,b=self.runs;target=Path(folder)/f'comparison-{self.data["reference"]["scenario_sha256"][:8]}-{self.data["current"]["scenario_sha256"][:8]}-D{self.data["cutoff"]:g}';export_comparison(a,b,self.data,self.figure,target,dict(reference=self.owner.run_annotation(a),current=self.owner.run_annotation(b)));self.owner.statusBar().showMessage(f'Comparison exported: {target}')
        except Exception as error:self.owner.statusBar().showMessage('Could not export comparison: '+str(error))
