"""Native controls for one-parameter, paired-seed tube studies."""
import copy
import threading
from pathlib import Path
import numpy as np
from PySide6.QtCore import QThread,Signal,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QLineEdit,QPushButton,
    QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox,QFileDialog)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
try:
    from .mesh_sweep import PARAMETERS,sweep_plan,run_sweep,load_sweep
    from .mesh_data import ROOT,load_mesh_run
except ImportError:
    from mesh_sweep import PARAMETERS,sweep_plan,run_sweep,load_sweep
    from mesh_data import ROOT,load_mesh_run


class SweepWorker(QThread):
    progress=Signal(int,int,object)
    completed=Signal(object)
    failed=Signal(str)
    def __init__(self,scene,settings,parameter,values,seeds,cutoff,parent):
        super().__init__(parent);self.scene=copy.deepcopy(scene);self.settings=copy.deepcopy(settings);self.parameter=parameter;self.values=values;self.seeds=seeds;self.cutoff=cutoff;self.cancel=threading.Event()
    def run(self):
        try:self.completed.emit(run_sweep(self.scene,self.settings,self.parameter,self.values,self.seeds,self.cutoff,cancel=self.cancel,progress=lambda i,n,row:self.progress.emit(i,n,row)))
        except Exception as error:self.failed.emit(str(error))


class SweepPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.worker=None;self.rows=[];self.folder=None
        layout=QVBoxLayout(self);intro=QLabel('Change one parameter while pairing runs by random seed. Other model controls and food sources are captured when the study starts. Each run saves all states; results below use one fixed cutoff.');intro.setWordWrap(True);layout.addWidget(intro)
        bar=QHBoxLayout();self.parameter=QComboBox()
        for key,label in PARAMETERS.items():self.parameter.addItem(label,key)
        bar.addWidget(self.parameter);bar.addWidget(QLabel('Values'));self.values=QLineEdit('1.15, 1.8, 2.2');bar.addWidget(self.values);bar.addWidget(QLabel('Seeds'));self.seeds=QLineEdit('42, 43, 47');bar.addWidget(self.seeds);layout.addLayout(bar)
        self.parameter.currentIndexChanged.connect(self.defaults)
        buttons=QHBoxLayout();self.start=QPushButton('Run parameter study');self.start.clicked.connect(self.begin);buttons.addWidget(self.start);self.cancel_button=QPushButton('Cancel study');self.cancel_button.setEnabled(False);self.cancel_button.clicked.connect(self.cancel);buttons.addWidget(self.cancel_button)
        open_run=QPushButton('Inspect selected run');open_run.clicked.connect(self.open_selected);buttons.addWidget(open_run);files=QPushButton('Open study files');files.clicked.connect(self.open_folder);buttons.addWidget(files);buttons.addStretch();layout.addLayout(buttons)
        open_study=QPushButton('Open saved study…');open_study.clicked.connect(self.open_study);buttons.insertWidget(2,open_study)
        self.status=QLabel('Ready · maximum 24 cases and 2 GB of raw states per study.');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.figure=Figure(figsize=(9,3),dpi=100,layout='constrained');self.canvas=FigureCanvasQTAgg(self.figure);self.axis=self.figure.add_subplot();self.plot();layout.addWidget(NavigationToolbar2QT(self.canvas,self));layout.addWidget(self.canvas,1)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['Value','Seed','Foods connected','Length km','Route/direct','One-break survival','Worst pair access'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(self.table,1)
        note=QLabel('Points are individual experiments. A small seed sample does not establish statistical reliability. Seed changes mesh, initial conductivity and forcing together; use matched seeds for parameter contrasts. Break survival is the explicitly defined one-break proxy.');note.setWordWrap(True);layout.addWidget(note)
    def defaults(self):
        self.values.setText({'gamma':'1.15, 1.8, 2.2','current':'0.2, 1, 2','spacing':'0.3, 0.45, 0.6','river_penalty':'0, 1, 2','dt':'0.05, 0.025, 0.0125'}[self.parameter.currentData()])
    def running(self):return self.worker is not None and self.worker.isRunning()
    def begin(self):
        if self.running() or (self.owner.worker and self.owner.worker.isRunning()):return
        try:
            values=[float(x.strip()) for x in self.values.text().split(',')];seeds=[int(x.strip()) for x in self.seeds.text().split(',')]
            settings=self.owner.settings();parameter=self.parameter.currentData();sweep_plan(settings,parameter,values,seeds)
        except Exception as error:QMessageBox.warning(self,'Study settings',str(error));return
        self.owner.pause();self.rows=[];self.folder=None;self.table.setRowCount(0);self.plot();cutoff=self.owner.cutoff.currentData()
        self.worker=SweepWorker(self.owner.scene,settings,parameter,values,seeds,cutoff,self);self.worker.progress.connect(self.progress);self.worker.completed.connect(self.complete);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.finished)
        self.start.setEnabled(False);self.parameter.setEnabled(False);self.values.setEnabled(False);self.seeds.setEnabled(False);self.owner.compute_button.setEnabled(False);self.cancel_button.setEnabled(True);self.status.setText(f'Computing {len(values)*len(seeds)} cases · D ≥ {cutoff:g}. Full records and summary.csv save incrementally.');self.worker.start()
    def progress(self,i,total,row):
        self.rows.append(row);j=self.table.rowCount();self.table.insertRow(j)
        route='Disconnected' if row['mean_route_direct_ratio'] is None else f"{row['mean_route_direct_ratio']:.4f}"
        worst='Not recorded' if 'worst_break_connected_pair_fraction' not in row else f"{row['worst_break_connected_pair_fraction']:.4f}"
        for k,value in enumerate([f"{row['value']:g}",str(row['seed']),f"{row['largest_food_component']}/{row['food_count']}",f"{row['length_km']:.3f}",route,f"{row['single_break_survival']:.4f}",worst]):self.table.setItem(j,k,QTableWidgetItem(value))
        self.folder=Path(row['run_folder']).parent.parent;self.status.setText(f"{i}/{total} complete · D ≥ {row['cutoff']:g} · {self.folder}");self.plot()
    def plot(self):
        self.axis.clear();self.axis.set_xlabel('Retained physical length (km)',fontsize=9);self.axis.set_ylabel('Mean food-pair route / direct distance',fontsize=9);self.axis.spines[['top','right']].set_visible(False);self.axis.grid(alpha=.15,lw=.5);self.axis.tick_params(labelsize=8)
        if self.rows:
            disconnected=sum(r['mean_route_direct_ratio'] is None for r in self.rows)
            self.axis.set_title(f'{len(self.rows)} runs · {disconnected} disconnected (route ratio unavailable)',loc='left',fontsize=9)
            values=sorted(set(row['value'] for row in self.rows));colors=['#297c65','#b97437','#426f9f','#9b5282','#707b37','#825d43','#478c96','#67578c']
            for i,value in enumerate(values):
                rows=[r for r in self.rows if r['value']==value and r['mean_route_direct_ratio'] is not None]
                self.axis.scatter([r['length_km'] for r in rows],[r['mean_route_direct_ratio'] for r in rows],s=38,c=colors[i%len(colors)],label=f'{value:g}',alpha=.85)
                for row in rows:self.axis.annotate(str(row['seed']),(row['length_km'],row['mean_route_direct_ratio']),xytext=(4,4),textcoords='offset points',fontsize=7)
            self.axis.legend(title=self.rows[0]['parameter'],fontsize=8,title_fontsize=8,frameon=False)
        self.canvas.draw_idle()
    def cancel(self):
        if self.worker:self.worker.cancel.set();self.status.setText('Cancelling; completed cases and available partial output will remain saved.')
    def complete(self,result):
        self.folder=Path(result['folder']);self.figure.savefig(self.folder/'study.svg');self.figure.savefig(self.folder/'study.png',dpi=180);self.status.setText(f"Complete · {len(result['rows'])} cases · D ≥ {result['plan']['cutoff']:g} · {self.folder}")
    def failed(self,error):
        self.status.setText(error)
        if not self.owner.closing:QMessageBox.warning(self,'Study stopped',error)
    def finished(self):
        worker=self.worker;self.worker=None
        if worker:worker.deleteLater()
        for widget in (self.start,self.parameter,self.values,self.seeds):widget.setEnabled(True)
        self.cancel_button.setEnabled(False);self.owner.compute_button.setEnabled(True)
        if self.owner.closing:self.owner.close()
    def open_selected(self):
        row=self.table.currentRow()
        if row<0 or row>=len(self.rows):return
        try:
            run=load_mesh_run(self.rows[row]['run_folder']);self.owner.scene=copy.deepcopy(run.scene);self.owner.refresh_pairs();self.owner.set_settings(run.settings);self.owner.cutoff.setCurrentIndex(self.owner.cutoff.findData(self.rows[row]['cutoff']));self.owner.accept_run(run);self.owner.final_state();self.owner.draft();self.owner.tabs.setCurrentIndex(0)
        except Exception as error:QMessageBox.warning(self,'Could not open study run',str(error))
    def open_folder(self):
        if self.folder:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder.resolve())))
    def open_study(self):
        if self.running():return
        folder=QFileDialog.getExistingDirectory(self,'Open parameter study',str(self.folder or ROOT/'results/mesh_sweeps'))
        if folder:
            try:self.apply_study(load_sweep(folder))
            except Exception as error:QMessageBox.warning(self,'Could not open study',str(error))
    def apply_study(self,result):
        if self.running():raise ValueError('Finish or cancel the current study before opening another.')
        plan=result['plan'];self.rows=[];self.table.setRowCount(0);self.parameter.setCurrentIndex(self.parameter.findData(plan['parameter']));self.values.setText(', '.join(str(v) for v in plan['values']));self.seeds.setText(', '.join(str(v) for v in plan['seeds']))
        self.owner.scene=copy.deepcopy(plan['scene']);self.owner.refresh_pairs();self.owner.set_settings(plan['base_settings']);self.owner.draft()
        for i,row in enumerate(result['rows']):self.progress(i+1,len(plan['cases']),row)
        self.folder=Path(result['folder']);state='complete' if result['complete'] else 'partial'
        self.status.setText(f"Loaded {state} study · {len(self.rows)} cases · D ≥ {plan['cutoff']:g}. Inspect a run to revalidate its complete dynamic record.")
