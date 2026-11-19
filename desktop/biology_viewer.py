"""Native laboratory for mechanistic exploratory growth, separate from transport."""
import json
from pathlib import Path
import time
import numpy as np
from PySide6.QtCore import QThread,QTimer,Qt,Signal
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QComboBox,QDoubleSpinBox,QSpinBox,QSlider,QProgressBar,QSplitter,QTabWidget,QTextBrowser,QFileDialog,QMessageBox,QScrollArea,QCheckBox)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
try:
    from .biology_data import ROOT,DEFAULT_BIOLOGY,run_biology,load_biology
    from .biology_plot import BiologyPlot
    from .biology_measures import BiologyMeasures
    from .biology_metrics import vein_metrics
except ImportError:
    from biology_data import ROOT,DEFAULT_BIOLOGY,run_biology,load_biology
    from biology_plot import BiologyPlot
    from biology_measures import BiologyMeasures
    from biology_metrics import vein_metrics

class BiologyWorker(QThread):
    completed=Signal(object);failed=Signal(str);progress=Signal(float)
    def __init__(self,settings,parent=None):super().__init__(parent);self.settings=settings
    def run(self):
        try:self.completed.emit(run_biology(self.settings,progress=self.progress.emit,cancelled=self.isInterruptionRequested))
        except Exception as e:self.failed.emit(str(e))

class BiologyViewer(QMainWindow):
    def __init__(self,auto_run=True):
        super().__init__();self.data=None;self.worker=None;self.index=0;self.children=[];self.setWindowTitle('Physarum — Biological growth laboratory');self.resize(1480,980);self.setMinimumSize(1150,780)
        self.setStyleSheet('QMainWindow,QWidget { background: #f6f7f3; color:#223b30; } QPushButton { padding:6px 10px; } QComboBox,QSpinBox,QDoubleSpinBox { padding:3px; background:#fff; } QTabWidget::pane { border:1px solid #cdd6ca; } QTextBrowser {background:#fff;}')
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root);heading=QLabel('BIOLOGICAL GROWTH  /  Exploratory migration');heading.setStyleSheet('font-size:19px;font-weight:600;padding:8px 2px;');layout.addWidget(heading)
        subtitle=QLabel('A moving margin, calcium-driven pressure changes and adaptive veins. A published-model benchmark with an explicit cooperative calcium variant.');subtitle.setWordWrap(True);layout.addWidget(subtitle)
        self.run_banner=QLabel('Prepare and compute a biological experiment.');self.run_banner.setWordWrap(True);layout.addWidget(self.run_banner)
        split=QSplitter();layout.addWidget(split,1);sidebar=QWidget();side=QVBoxLayout(sidebar);side.setContentsMargins(5,10,12,5)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.Shape.NoFrame);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);controls=QWidget();form=QFormLayout(controls);form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow);form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows);scroll.setWidget(controls);side.addWidget(scroll,1)
        self.controls={};self.preset=QComboBox();self.preset.addItems(['Choose a control preset…','Fast-front variant · τ₂ = 2','Source front timescale · τ₂ = 20','No vein–front feedback · k = 0','Printed calcium control · Hill 1']);form.addRow('Preset',self.preset);self.arena=QComboBox();self.arena.addItem('Bent corridor · source benchmark','snake');self.arena.addItem('Straight corridor · control','straight');form.addRow('Arena',self.arena)
        self.hill=QComboBox();self.hill.addItem('Cooperative Hill 4 · oscillator variant',4);self.hill.addItem('Printed Hill 1 · nonoscillating control',1);form.addRow('Calcium response',self.hill)
        self.integrator=QComboBox();self.integrator.addItem('Midpoint / CN · refined integration','midpoint');self.integrator.addItem('Legacy split · archived reference','legacy');self.integrator.setCurrentIndex(self.integrator.findData(DEFAULT_BIOLOGY['integrator']));form.addRow('Integration method',self.integrator)
        for key,label,low,high,step,decimals in [('duration','Duration',8,1600,80,5),('dt','Time step',.005,.04,.005,5),('spacing','Mesh spacing',.35,1,.05,2),('tau_front','Front timescale τ₂',2,40,2,1),('feedback','Vein → front feedback k',0,.1,.005,3),('save_interval','Save fields every',.1,40,2,5)]:
            box=QDoubleSpinBox();box.setRange(low,high);box.setSingleStep(step);box.setDecimals(decimals);box.setValue(DEFAULT_BIOLOGY[key]);self.controls[key]=box;form.addRow(label,box)
        seed=QSpinBox();seed.setRange(0,2**31-1);seed.setValue(42);self.controls['seed']=seed;form.addRow('Mesh seed',seed)
        intro=QLabel('START HERE\nCompute the corridor, then press Play. Olive marks the advancing band. The body accumulates behind it; fine gold segments show actual vein conductivity.\n\nCalcium changes drive pressure, which drives flow. Flow can reinforce a vein only where the body gate is open. The lower plot resolves the fast oscillations separately from the slower growth frames.');intro.setWordWrap(True);form.addRow(intro)
        self.stats=QLabel('No biological experiment loaded.');self.stats.setWordWrap(True);side.addWidget(self.stats)
        self.draft_label=QLabel('Controls prepare the next experiment. The displayed record keeps its original parameters.');self.draft_label.setWordWrap(True);form.addRow(self.draft_label)
        self.preview=QPushButton('Run short growth experiment · ≈80 units');self.preview.setToolTip('Uses the same equations, mesh and time step; stops earlier and saves more growth frames.');self.preview.clicked.connect(self.preview_run);side.addWidget(self.preview)
        self.compute=QPushButton('Compute biological experiment');self.compute.clicked.connect(self.run);side.addWidget(self.compute)
        row=QHBoxLayout();self.cancel=QPushButton('Cancel computation');self.cancel.setEnabled(False);self.cancel.clicked.connect(self.cancel_run);row.addWidget(self.cancel);open_button=QPushButton('Open record…');open_button.clicked.connect(self.open);row.addWidget(open_button);side.addLayout(row)
        self.progress=QProgressBar();self.progress.setVisible(False);side.addWidget(self.progress);sidebar.setMinimumWidth(310);sidebar.setMaximumWidth(390);split.addWidget(sidebar)
        right=QWidget();panel=QVBoxLayout(right);panel.setContentsMargins(0,0,0,0);self.tabs=QTabWidget();panel.addWidget(self.tabs,1);view=QWidget();vl=QVBoxLayout(view);self.tabs.addTab(view,'Colony and veins')
        bar=QHBoxLayout();self.mode=QComboBox();self.mode.addItems(['Body + veins','Advancing margin','Calcium']);bar.addWidget(self.mode);self.follow=QCheckBox('Follow colony');self.follow.setChecked(True);self.follow.toggled.connect(lambda:self.display(self.index));bar.addWidget(self.follow);bar.addWidget(QLabel('Display D ≥'));self.cutoff=QDoubleSpinBox();self.cutoff.setRange(.001,100);self.cutoff.setDecimals(3);self.cutoff.setSingleStep(.05);self.cutoff.setValue(1.);bar.addWidget(self.cutoff);bar.addStretch();export=QPushButton('Export figure / fields…');export.clicked.connect(self.export);bar.addWidget(export);vl.addLayout(bar)
        self.figure=Figure(figsize=(11,8),layout='constrained');self.canvas=FigureCanvasQTAgg(self.figure);self.plot=BiologyPlot(self.figure);vl.addWidget(NavigationToolbar2QT(self.canvas,self));vl.addWidget(self.canvas,1)
        self.measures=BiologyMeasures();self.tabs.addTab(self.measures,'Vein measurements')
        self.notes=QTextBrowser();self.notes.setOpenExternalLinks(True);self.tabs.addTab(self.notes,'Equations and interpretation');self.record=QTextBrowser();self.tabs.addTab(self.record,'Recorded experiment')
        playback=QHBoxLayout();self.play=QPushButton('Play growth');self.play.setCheckable(True);self.play.toggled.connect(lambda value:self.play.setText('Pause growth' if value else 'Play growth'));playback.addWidget(self.play);restart=QPushButton('Restart');restart.clicked.connect(lambda:self.slider.setValue(0));playback.addWidget(restart);self.frame_label=QLabel('');playback.addWidget(self.frame_label);playback.addStretch();playback.addWidget(QLabel('Playback frames/s'));self.speed=QSpinBox();self.speed.setRange(1,30);self.speed.setValue(8);playback.addWidget(self.speed);panel.addLayout(playback)
        self.slider=QSlider(Qt.Orientation.Horizontal);self.slider.setRange(0,0);self.slider.valueChanged.connect(self.display);panel.addWidget(self.slider);self.mode.currentIndexChanged.connect(lambda:self.display(self.index));self.cutoff.valueChanged.connect(lambda:self.display(self.index));split.addWidget(right);split.setSizes([340,1140])
        menu=self.menuBar().addMenu('Other models');menu.addAction('London tube adaptation…',self.open_transport);menu.addAction('Earlier particle experiment…',self.open_particles)
        self.timer=QTimer(self);self.timer.setInterval(25);self.timer.timeout.connect(self.tick);self.timer.start();self.last_tick=time.monotonic();self.credit=0.
        for control in self.controls.values():control.valueChanged.connect(self.draft)
        for control in (self.arena,self.hill,self.integrator):control.currentIndexChanged.connect(self.draft)
        self.preset.currentIndexChanged.connect(self.apply_preset)
        self.notes.setHtml('''<h2>What this experiment does</h2><p>The reaction–diffusion fields u and v move an advancing margin. A body proxy w accumulates behind it. Calcium c and phosphorylation φ generate pressure changes; a compliant, inertial network carries signed flow q. Conductivity D grows in occupied regions when flow reinforces it and otherwise decays.</p><p><b>It is an exploratory model, not a validated digital organism.</b> The body does not retract, and the published model assumes an ample supply from the rear. Neither biomass nor nutrient consumption is conserved. The chemical fields and regularized fluid background are defined over the entire computational arena, including unoccupied regions; only vein reinforcement is body-gated. This is a coarse-grained construction, not resolved cell chemistry. There are no food sources in this corridor benchmark. London and food-site design remain in the separate tube experiment.</p><h3>Calcium controls</h3><p>The 2017 printed activation has Hill exponent 1. With the listed coefficients its isolated oscillator settles. The default uses the faster front timescale τ₂ = 2 and explicitly restores exponent 4 from Smith &amp; Saldana (1992); it is a variant and has not reproduced the later paper’s results quantitatively. Try exponent 1 and k = 0 as controls.</p><h3>Equations</h3><p>τ₁ ċ = F(c,φ) + D꜀ Δc; τ₁ φ̇ = G(c,φ) + Dφ Δφ<br>u̇ = (Dᵤ Δu − uv²)/τ₂<br>v̇ = (Dᵥ Δv + uv² − α₁v)/τ₂ + k B(w) ΣD<br>ẇ = α₂v/τ₂<br>L̃ q̇ = pᵢ − pⱼ − R̃q<br>ṗⱼ = Σᵢ qᵢⱼ/Ĉᵢⱼ − κ(cⱼ − c̄)<br>Ḋ = Γ(w) |q|¹·³/(1 + 0.01|q|¹·³) − 0.15D</p><p>Γ = 1 for average w &gt; 1. B = 1 for 0.1 ≤ w ≤ 0.9. Wall compliance Ĉ = (0.1 + 0.03D³⁄⁴)(1 + 0.01v)/edge length.</p><h3>Numerics and display</h3><p>Seeded triangular mesh; lumped linear finite elements; no-flux boundaries. Legacy integration uses split RK4 reactions and backward-Euler diffusion with lagged coupling; it is first order. The midpoint option uses Strang reaction–diffusion with Crank–Nicolson diffusion and damped startup, plus midpoint conductivity, activator and body coupling. It approaches second order in a resolved smooth test, but stiff splitting and body gates still require refinement. Neither method establishes biological validity. All D values remain in the record; the display cutoff does not prune the simulation. Thin strokes use D¼. Body colour is a model field, not a microscopy prediction. Slow full-field snapshots cannot resolve individual contractions; the probe is recorded every integration step.</p><p><a href="https://doi.org/10.1088/1361-6463/aa88e9">Schenz et al. (2017), Routing while scouting</a><br><a href="https://doi.org/10.1016/S0006-3495(92)81843-X">Smith &amp; Saldana (1992), calcium oscillator</a></p>''')
        if auto_run:QTimer.singleShot(0,self.start_default)
    def apply_preset(self,index):
        if index==0:return
        index-=1
        self.controls['tau_front'].setValue(20 if index==1 else 2);self.controls['feedback'].setValue(0 if index==2 else .01);self.hill.setCurrentIndex(1 if index==3 else 0);self.preset.blockSignals(True);self.preset.setCurrentIndex(0);self.preset.blockSignals(False)
    def settings(self):return dict(arena=self.arena.currentData(),hill=self.hill.currentData(),integrator=self.integrator.currentData(),**{k:(v.value() if k!='seed' else int(v.value())) for k,v in self.controls.items()})
    def draft(self,*_):
        if not self.data:return
        saved={**self.data['settings'],'integrator':self.data['settings'].get('integrator','legacy')}
        changed=self.settings()!=saved
        self.run_banner.setText('UNAPPLIED CHANGES · Showing the saved run. Compute again to apply these controls.' if changed else f"RECORDED EXPERIMENT · {saved['integrator']} · mesh seed {saved['seed']} · duration {saved['duration']:g}")
        self.run_banner.setStyleSheet('padding:5px;background:#fff0cc;color:#725317;' if changed else 'padding:5px;background:#e8eee3;color:#36523d;')
    def start_default(self):
        # Reuse only a complete current-settings record. The record contains its source.
        for folder in sorted((ROOT/'results/biology_runs').glob('*'),reverse=True):
            try:
                manifest=json.loads((folder/'scenario.json').read_text())
                if manifest.get('settings')!=DEFAULT_BIOLOGY:continue
                # Match current C++ sources so old developmental engines cannot become a demo.
                if any((ROOT/name).read_bytes()!= (folder/'source'/name).read_bytes() for name in manifest['software']['source_sha256'] if name=='CMakeLists.txt' or name.startswith(('src/','include/'))):continue
                self.accept(load_biology(folder));return
            except (OSError,KeyError,ValueError):continue
        self.run()
    def preview_run(self):
        dt=self.controls['dt'].value();self.controls['duration'].setValue(round(80/dt)*dt);self.controls['save_interval'].setValue(round(1/dt)*dt);self.run()
    def run(self):
        if self.worker and self.worker.isRunning():return
        self.play.setChecked(False);self.compute.setEnabled(False);self.preview.setEnabled(False);self.cancel.setEnabled(True);self.progress.setValue(0);self.progress.show();self.statusBar().showMessage('Computing the coupled C++ growth model; each run is saved automatically.');self.worker=BiologyWorker(self.settings(),self);self.worker.progress.connect(lambda f:self.progress.setValue(round(100*f)));self.worker.completed.connect(self.accept);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.finished);self.worker.start()
    def cancel_run(self):
        if self.worker:self.worker.requestInterruption();self.cancel.setEnabled(False)
    def finished(self):self.compute.setEnabled(True);self.preview.setEnabled(True);self.cancel.setEnabled(False);self.progress.hide()
    def failed(self,message):QMessageBox.warning(self,'Biological experiment',message);self.statusBar().showMessage(message)
    def accept(self,data):
        previous=self.data
        self.previous=previous
        self.data=data;self.play.setChecked(False);self.plot.setup(data);self.measures.setup(data);
        if previous and previous['settings']['arena']==data['settings']['arena']:
            old=previous['history'];self.plot.coverage.plot(old['time'],100*old['body_area']/previous['mass'].sum(),color='#8a7966',lw=1.,ls='--',label='Previous recorded run');self.plot.coverage.legend(fontsize=7,frameon=False,loc='lower right')
        self.slider.setRange(0,len(data['history'])-1);self.slider.setValue(0);self.display(0);s=data['settings'];self.arena.setCurrentIndex(self.arena.findData(s['arena']));self.hill.setCurrentIndex(self.hill.findData(s['hill']));self.integrator.setCurrentIndex(self.integrator.findData(s.get('integrator','legacy')))
        for k,v in self.controls.items():v.setValue(s[k])
        self.record.setPlainText('SAVED BIOLOGICAL EXPERIMENT\n'+str(data['folder'])+'\n\n'+json.dumps(dict(settings=s,engine=data['engine'],discretization=data['manifest']['discretization']),indent=2)+'\n\nChecksums and original source are saved in scenario.json and source/. This record retains all eight fields, the full-rate probe, mesh and diagnostics.');self.statusBar().showMessage('Saved record: '+str(data['folder']));self.draft()
    def display(self,index):
        if not self.data:return
        self.index=index;m=self.plot.display(index,self.mode.currentText(),self.cutoff.value(),self.follow.isChecked());self.frame_label.setText(f"t = {m['time']:g} / {self.data['settings']['duration']:g}");self.stats.setText(f"DISPLAYED RECORD · occupied {100*m['area']/m['total']:.1f}%\nVein segments: {m['veins']:,} · D max: {m['max_d']:.3g}\nHill exponent: {self.data['settings']['hill']} · dt: {self.data['settings']['dt']:g} · k: {self.data['settings']['feedback']:g}\nIntegrator: {self.data['settings'].get('integrator','legacy')}");
        metric=vein_metrics(self.data['xy'],self.data['edges'],self.data['fields']['d'][index],self.data['inoculum'],self.data['settings']['arena'],self.cutoff.value());fraction=metric['inoculum_attached_fraction'];connection='No retained veins' if fraction is None else f"Inoculum-attached length: {100*fraction:.1f}%";self.stats.setText(self.stats.text()+f"\nRetained components: {metric['components']} · {connection}");self.canvas.draw_idle();self.measures.display(m['time'])
    def tick(self):
        now=time.monotonic();elapsed=now-self.last_tick;self.last_tick=now
        if not self.play.isChecked() or not self.data:self.credit=0;return
        self.credit+=elapsed*self.speed.value()
        if self.credit>=1:
            step=int(self.credit);self.credit-=step;self.slider.setValue(min(self.slider.maximum(),self.index+step))
            if self.index>=self.slider.maximum():self.play.setChecked(False)
    def open(self):
        folder=QFileDialog.getExistingDirectory(self,'Open biological experiment',str(ROOT/'results/biology_runs'))
        if folder:
            try:self.accept(load_biology(folder))
            except Exception as e:self.failed(str(e))
    def export(self):
        if not self.data:return
        folder=QFileDialog.getExistingDirectory(self,'Export current frame and fields',str(ROOT/'results'))
        if not folder:return
        try:
            target=Path(folder)/f"biology-frame-{self.index:04d}-{time.time_ns()}";target.mkdir();self.figure.savefig(target/'colony.png',dpi=220);self.figure.savefig(target/'colony.svg');r=self.data
            np.savetxt(target/'node-fields.csv',np.column_stack([np.arange(len(r['xy'])),r['xy'],r['mass'],r['inoculum'].astype(int)]+[r['fields'][n][self.index] for n in ('c','phi','u','v','w','p')]),delimiter=',',header='id,x,y,mass,inoculum,c,phi,u,v,w,p',comments='')
            np.savetxt(target/'veins.csv',np.column_stack([r['edges']]+[r['fields'][n][self.index] for n in ('q','d')]),delimiter=',',header='from,to,length,diffusion_weight,q,d',comments='');(target/'snapshot.json').write_text(json.dumps(dict(source_record=str(r['folder']),source_fingerprint=r['engine']['source_fingerprint'],model=r['engine']['model'],discretization=r['manifest']['discretization'],vein_diagnostics=vein_metrics(r['xy'],r['edges'],r['fields']['d'][self.index],r['inoculum'],r['settings']['arena'],self.cutoff.value()),comparison_settings=self.previous['settings'] if self.previous else None,comparison_record=str(self.previous['folder']) if self.previous else None,time=float(r['history']['time'][self.index]),display_cutoff=self.cutoff.value(),settings=r['settings']),indent=2)+'\n');
            for name in ('history.csv','probe.csv','global.csv'):
                original=r['folder']/'raw'/name
                if original.exists():(target/name).write_bytes(original.read_bytes())
            if self.previous and self.previous['settings']['arena']==r['settings']['arena']:(target/'comparison-history.csv').write_bytes((self.previous['folder']/'raw/history.csv').read_bytes())
            if r.get('global_history') is not None:self.measures.figure.savefig(target/'vein-measurements.png',dpi=220);self.measures.figure.savefig(target/'vein-measurements.svg')
            self.statusBar().showMessage('Exported: '+str(target))
        except Exception as e:self.failed(str(e))
    def open_transport(self):
        try:from .mesh_viewer import MeshViewer
        except ImportError:from mesh_viewer import MeshViewer
        window=MeshViewer();window.show();self.children.append(window)
    def open_particles(self):
        try:from .growth_viewer import GrowthViewer
        except ImportError:from growth_viewer import GrowthViewer
        window=GrowthViewer();window.show();self.children.append(window)
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():self.worker.requestInterruption();event.ignore();self.statusBar().showMessage('Cancelling computation; close again after it stops.');return
        self.timer.stop();event.accept()
