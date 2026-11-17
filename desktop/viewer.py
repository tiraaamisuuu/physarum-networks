#!/usr/bin/env python3
"""Native Qt viewer for discrete states produced by the C++ Phase 1 model."""
import argparse
import math
from pathlib import Path
import sys
import time

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
                               QSlider, QSpinBox, QSplitter, QStyle, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget, QHeaderView)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import numpy as np

try:
    from .run_data import ROOT, DEFAULTS, load_run, run_experiment, save_run, validate_parameters
    from .qt_compat import prepare_platform_plugins
except ImportError:
    from run_data import ROOT, DEFAULTS, load_run, run_experiment, save_run, validate_parameters
    from qt_compat import prepare_platform_plugins

SHORT, LONG = "#245f8a", "#ae572d"


def number(value):
    return f"{value:.3e}" if value != 0 and abs(value) < 1e-4 else f"{value:.6g}"


def readonly_table(headers, rows):
    table = QTableWidget(rows, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().hide()
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setAlternatingRowColors(True)
    for row in range(rows):
        for column in range(len(headers)):
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, column, item)
    return table


class Runner(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, executable, parameters, parent=None):
        super().__init__(parent)
        self.executable, self.parameters = executable, parameters

    def run(self):
        try:
            self.completed.emit(run_experiment(self.executable, self.parameters))
        except Exception as error:
            self.failed.emit(str(error))


class StateFigure(FigureCanvasQTAgg):
    """Widths, labels and plot cursors are updated from the same discrete frame."""
    def __init__(self):
        self.figure = Figure(figsize=(10, 5), dpi=100, layout="constrained", facecolor="white")
        super().__init__(self.figure)
        self.setMinimumSize(600, 360)
        self.data = None
        self.geometry = np.array([[0., 0.], [1., .72], [1., -.72], [2., 0.]])
        self.figure.text(.5, .5, "Run an experiment or open a recorded run.", ha="center", color="#555")

    def set_run(self, data):
        self.data = data
        self.figure.clear()
        grid = self.figure.add_gridspec(2, 2, width_ratios=[1.12, 1])
        self.network = self.figure.add_subplot(grid[:, 0])
        self.d_axis = self.figure.add_subplot(grid[0, 1])
        self.q_axis = self.figure.add_subplot(grid[1, 1], sharex=self.d_axis)
        self.network.set_title("Network state", fontsize=11, loc="left", pad=12)
        self.network.set_aspect("equal")
        self.network.set(xlim=(-.55, 2.55), ylim=(-1.2, 1.2))
        self.network.axis("off")
        self.lines, self.pressures = [], []
        for edge in data.edges:
            coordinates = self.geometry[[edge["from"], edge["to"]]]
            self.network.plot(*coordinates.T, color="#d3d9dd", lw=1.1, zorder=1)
            line, = self.network.plot(*coordinates.T, color=SHORT if edge["id"]<2 else LONG,
                                      solid_capstyle="round", zorder=2)
            self.lines.append(line)
        self.network.scatter(*self.geometry.T, s=260, color="white", edgecolors="#333", zorder=3)
        for i, (x, y) in enumerate(self.geometry):
            self.network.text(x, y, str(i), ha="center", va="center", fontsize=10, zorder=4)
            px,py,align = (x-.02,y+.18,"right") if i==0 else (x+.02,y+.18,"left") if i==3 else (x,y+.16,"center") if i==1 else (x,y-.16,"center")
            self.pressures.append(self.network.text(px,py,"",ha=align,fontsize=8,color="#333"))
        source, sink = int(data.parameters["source"]), int(data.parameters["sink"])
        for node, label in ((source, "source"), (sink, "sink")):
            x, y = self.geometry[node]
            self.network.text(x, y-.29, label, ha="center", fontsize=9)
        short_length = sum(e["length"] for e in data.edges[:2])
        long_length = sum(e["length"] for e in data.edges[2:])
        self.short_label = self.network.text(1, 1.02, f"Short route: L = {short_length:g}", ha="center", fontsize=9, color=SHORT)
        self.long_label = self.network.text(1, -1.02, f"Long route: L = {long_length:g}", ha="center", fontsize=9, color=LONG)
        self.network.text(1, -1.18, "Schematic layout; width ∝ D. Pale outlines retain every edge.",
                          ha="center", fontsize=7.5, color="#555")
        times = [frame["time"] for frame in data.frames]
        self.cursors, self.markers = [], []
        for axis, key, label in ((self.d_axis,"d","Conductivity D"),(self.q_axis,"q","Signed flow Q")):
            for edge, color, route in ((0,SHORT,"Short route"),(2,LONG,"Long route")):
                axis.plot(times, [frame[key][edge] for frame in data.frames], color=color, lw=1.5, label=route)
            axis.set_ylabel(label, fontsize=9)
            axis.tick_params(labelsize=8)
            axis.grid(alpha=.2, lw=.6)
            axis.spines[["top","right"]].set_visible(False)
            axis.set_xlim(0,data.parameters["duration"])
            values = [value for frame in data.frames for value in frame[key]]
            low,high = min(0,min(values)),max(values)
            span = max(high-low,1e-12)
            axis.set_ylim(low-.03*span,high+.12*span)
            self.cursors.append(axis.axvline(0, color="#555", ls="--", lw=.8))
            self.markers.append([axis.plot([],[],"o",color=color,ms=4)[0] for color in (SHORT,LONG)])
        self.d_axis.legend(fontsize=8,loc="best",frameon=False)
        self.d_axis.set_title("Full recorded trajectories; cursor selects the displayed state",fontsize=9,loc="left",pad=12)
        self.q_axis.set_xlabel("Time (arbitrary model units)",fontsize=9)
        self.set_frame(0)

    def set_frame(self, index):
        if self.data is None:
            return
        frame = self.data.frames[index]
        for edge, line in enumerate(self.lines):
            # A rendering cutoff only: numerical D and all underlying edges are preserved.
            line.set_linewidth(12*frame["d"][edge] if frame["d"][edge] >= 1e-10 else 0)
        for node, label in enumerate(self.pressures):
            label.set_text(f"p = {number(frame['p'][node])}")
        self.short_label.set_text(f"Short route: L = {sum(e['length'] for e in self.data.edges[:2]):g}; D = {number(frame['d'][0])}")
        self.long_label.set_text(f"Long route: L = {sum(e['length'] for e in self.data.edges[2:]):g}; D = {number(frame['d'][2])}")
        for key, cursor, markers in zip(("d","q"),self.cursors,self.markers):
            cursor.set_xdata([frame["time"],frame["time"]])
            for edge, marker in zip((0,2),markers):
                marker.set_data([frame["time"]],[frame[key][edge]])
        self.draw_idle()


class Viewer(QMainWindow):
    def __init__(self, executable=None, auto_run=True):
        super().__init__()
        self.executable = Path(executable or ROOT/"build/physarum_run")
        self.data = None
        self.index = 0
        self.worker = None
        self.playing = False
        self.playhead = 0.
        self.last_tick = time.monotonic()
        self.setWindowTitle("Physarum Network Viewer — Phase 1")
        self.resize(1320,850)
        self.setMinimumSize(1000,680)
        self.controls = {}
        self.build_ui()
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        if auto_run:
            QTimer.singleShot(0,self.run)

    def build_ui(self):
        menu = self.menuBar().addMenu("&File")
        self.open_folder_action = QAction("Open run &folder…",self)
        self.open_folder_action.triggered.connect(self.open_folder)
        menu.addAction(self.open_folder_action)
        self.open_archive_action = QAction("&Open saved run…",self)
        self.open_archive_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_archive_action.triggered.connect(self.open_archive)
        menu.addAction(self.open_archive_action)
        self.save_action = QAction("&Save run archive…",self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save)
        self.save_action.setEnabled(False)
        menu.addAction(self.save_action)
        menu.addSeparator()
        close = menu.addAction("Close")
        close.setShortcut(QKeySequence.StandardKey.Close)
        close.triggered.connect(self.close)
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction("Model and viewer notes…").triggered.connect(self.show_notes)

        central = QSplitter(Qt.Orientation.Horizontal)
        settings_widget = QWidget()
        settings = QVBoxLayout(settings_widget)
        settings.setContentsMargins(14,14,14,14)
        group = QGroupBox("Experiment parameters")
        form = QFormLayout(group)
        definitions = [("current","Injected flow I₀",.1,5.,.1,3),
                       ("gamma","Response γ",.5,3.,.1,3),
                       ("dt","Time step Δt",.005,.25,.005,4),
                       ("duration","Duration",1.,60.,1.,3),
                       ("initial_conductivity","Initial D",.01,1.,.05,3)]
        for key,label,low,high,step,decimals in definitions:
            control = QDoubleSpinBox()
            control.setObjectName(key)
            control.setRange(low,high)
            control.setDecimals(decimals)
            control.setSingleStep(step)
            control.setValue(DEFAULTS[key])
            control.valueChanged.connect(self.parameters_changed)
            self.controls[key] = control
            form.addRow(label,control)
        form.addRow("Source → sink",QLabel("0 → 3 (fixed)"))
        settings.addWidget(group)
        self.run_button = QPushButton("Run experiment")
        self.run_button.setObjectName("run")
        self.run_button.setShortcut("Ctrl+R")
        self.run_button.clicked.connect(self.run)
        settings.addWidget(self.run_button)
        self.defaults_button = QPushButton("Baseline defaults")
        self.defaults_button.clicked.connect(self.defaults)
        settings.addWidget(self.defaults_button)
        self.parameter_note = QLabel("Parameters apply when a new experiment is run.")
        self.parameter_note.setWordWrap(True)
        settings.addWidget(self.parameter_note)
        settings.addSpacing(14)
        scope = QLabel("Phase 1 fixture\n\nFour fixed nodes; routes of length 2 and 4.\n\nThe C++ engine computes the states. The viewer displays those states without interpolation.\n\nThis is not a reproduction of the Tokyo experiment.")
        scope.setWordWrap(True)
        settings.addWidget(scope)
        settings.addStretch()
        save = QPushButton("Save run archive…")
        save.clicked.connect(self.save)
        self.save_button = save
        save.setEnabled(False)
        settings.addWidget(save)
        central.addWidget(settings_widget)

        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(5,10,12,10)
        self.provenance = QLabel("No run loaded")
        self.provenance.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.provenance)
        vertical = QSplitter(Qt.Orientation.Vertical)
        plot_panel = QWidget()
        plot_layout = QVBoxLayout(plot_panel)
        plot_layout.setContentsMargins(0,0,0,0)
        self.canvas = StateFigure()
        self.navigation = NavigationToolbar2QT(self.canvas,self)
        plot_layout.addWidget(self.navigation)
        plot_layout.addWidget(self.canvas)
        vertical.addWidget(plot_panel)

        self.inspector = QTabWidget()
        self.edges_table = readonly_table(["Edge","From → to","Length L","Conductivity D","Signed flow Q"],4)
        self.nodes_table = readonly_table(["Node","Role","Pressure p"],4)
        self.checks_table = readonly_table(["Numerical check","Current state","Worst across run","Acceptance limit"],3)
        self.inspector.addTab(self.edges_table,"Edges")
        self.inspector.addTab(self.nodes_table,"Nodes")
        self.inspector.addTab(self.checks_table,"Solver diagnostics")
        self.inspector.setMinimumHeight(145)
        vertical.addWidget(self.inspector)
        vertical.setSizes([490,180])
        layout.addWidget(vertical,1)

        playback = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("play")
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.clicked.connect(self.toggle_play)
        playback.addWidget(self.play_button)
        self.restart_button = QPushButton("Restart")
        self.restart_button.clicked.connect(self.restart)
        playback.addWidget(self.restart_button)
        self.step_button = QPushButton("Step +1")
        self.step_button.setObjectName("step_forward")
        self.step_button.clicked.connect(self.step_forward)
        playback.addWidget(self.step_button)
        playback.addStretch()
        playback.addWidget(QLabel("Playback rate:"))
        self.speed = QComboBox()
        self.speed.setObjectName("playback_rate")
        for value in (.25,.5,1.,2.,4.):
            self.speed.addItem(f"{value:g} model units/s",value)
        self.speed.setCurrentIndex(2)
        playback.addWidget(self.speed)
        layout.addLayout(playback)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setObjectName("timeline")
        self.timeline.setRange(0,600)
        self.timeline.valueChanged.connect(self.scrub)
        layout.addWidget(self.timeline)
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step:"))
        self.step_spin = QSpinBox()
        self.step_spin.setObjectName("step_index")
        self.step_spin.setRange(0,600)
        self.step_spin.valueChanged.connect(self.scrub)
        step_layout.addWidget(self.step_spin)
        self.time_label = QLabel("t = 0.00")
        self.time_label.setObjectName("model_time")
        step_layout.addWidget(self.time_label)
        step_layout.addStretch()
        step_layout.addWidget(QLabel("Paired route edges overlap in the trajectory plots."))
        layout.addLayout(step_layout)
        central.addWidget(right)
        central.setSizes([250,1070])
        self.setCentralWidget(central)
        self.set_playback_enabled(False)
        self.statusBar().showMessage("C++20 / Eigen simulation; native Qt viewer")

    def set_playback_enabled(self, enabled):
        for widget in (self.play_button,self.restart_button,self.step_button,self.timeline,self.step_spin,self.speed):
            widget.setEnabled(enabled)

    def parameters_changed(self):
        if self.data:
            changed = any(control.value() != self.data.parameters[key] for key,control in self.controls.items())
            changed = changed or self.data.parameters['source'] != 0 or self.data.parameters['sink'] != 3
            self.parameter_note.setText("Controls differ from the displayed run. Run to apply; the displayed data is unchanged." if changed
                                        else "Controls match the displayed experiment.")

    def defaults(self):
        for key,value in DEFAULTS.items():
            self.controls[key].setValue(value)
        self.parameters_changed()

    def run(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.executable.is_file():
            QMessageBox.critical(self,"C++ runner missing","Build the project first:\ncmake -S . -B build -DCMAKE_BUILD_TYPE=Release\ncmake --build build --parallel")
            return
        payload = {key:control.value() for key,control in self.controls.items()}
        try:
            validate_parameters(payload)
        except ValueError as error:
            QMessageBox.warning(self,"Invalid experiment",str(error))
            return
        self.pause()
        self.run_button.setEnabled(False)
        self.defaults_button.setEnabled(False)
        for control in self.controls.values():
            control.setEnabled(False)
        self.open_folder_action.setEnabled(False)
        self.open_archive_action.setEnabled(False)
        self.statusBar().showMessage("Running C++ experiment…")
        self.worker = Runner(self.executable,payload,self)
        self.worker.completed.connect(self.set_run)
        self.worker.failed.connect(self.run_failed)
        self.worker.finished.connect(self.run_finished)
        self.worker.start()

    def run_finished(self):
        self.run_button.setEnabled(True)
        self.defaults_button.setEnabled(True)
        for control in self.controls.values():
            control.setEnabled(True)
        self.open_folder_action.setEnabled(True)
        self.open_archive_action.setEnabled(True)

    def run_failed(self, message):
        self.statusBar().showMessage("Experiment failed; the previous run has been retained.")
        QMessageBox.critical(self,"Experiment failed",message)

    def set_run(self, data):
        self.pause()
        self.data = data
        self.index = 0
        self.playhead = 0.
        self.canvas.set_run(data)
        self.navigation.update()
        self.timeline.blockSignals(True)
        self.step_spin.blockSignals(True)
        self.timeline.setRange(0,len(data.frames)-1)
        self.step_spin.setRange(0,len(data.frames)-1)
        self.timeline.blockSignals(False)
        self.step_spin.blockSignals(False)
        for key,control in self.controls.items():
            control.blockSignals(True)
            control.setValue(data.parameters[key])
            control.blockSignals(False)
        p = data.parameters
        self.provenance.setText(f"{data.origin}\nI₀={p['current']:g}, γ={p['gamma']:g}, Δt={p['dt']:g}, D₀={p['initial_conductivity']:g}, {int(p['source'])} → {int(p['sink'])}, {len(data.frames)} states")
        self.parameters_changed()
        self.set_playback_enabled(True)
        self.save_action.setEnabled(True)
        self.save_button.setEnabled(True)
        self.worst = (max(f["conservation"] for f in data.frames),max(f["backward_error"] for f in data.frames),min(f["rcond"] for f in data.frames))
        self.display_frame(0)
        self.statusBar().showMessage("Run loaded. Press Play to animate the discrete states.")

    def display_frame(self, index):
        if not self.data:
            return
        self.index = max(0,min(int(index),len(self.data.frames)-1))
        frame = self.data.frames[self.index]
        self.canvas.set_frame(self.index)
        for widget in (self.timeline,self.step_spin):
            widget.blockSignals(True)
            widget.setValue(self.index)
            widget.blockSignals(False)
        self.time_label.setText(f"t = {frame['time']:.4f} / {self.data.parameters['duration']:g} model units")
        for edge in self.data.edges:
            i = edge["id"]
            for column,value in enumerate((str(i),f"{edge['from']} → {edge['to']}",number(edge["length"]),number(frame["d"][i]),number(frame["q"][i]))):
                self.edges_table.item(i,column).setText(value)
        for node in range(4):
            role = "source" if node==self.data.parameters["source"] else "sink" if node==self.data.parameters["sink"] else "junction"
            for column,value in enumerate((str(node),role,number(frame["p"][node]))):
                self.nodes_table.item(node,column).setText(value)
        limits = (1e-12+1e-10*self.data.parameters["current"],1e-12,1e-14)
        for row,(name,key) in enumerate((("Conservation ∞-norm","conservation"),("Pressure backward error","backward_error"),("Scaled reciprocal condition","rcond"))):
            for column,value in enumerate((name,number(frame[key]),number(self.worst[row]),("≥ " if row==2 else "≤ ")+number(limits[row]))):
                self.checks_table.item(row,column).setText(value)

    def scrub(self, index):
        self.pause()
        self.display_frame(index)
        if self.data:
            self.playhead = self.data.frames[self.index]["time"]

    def pause(self):
        self.playing = False
        self.play_button.setText("Play")
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def toggle_play(self):
        if not self.data:
            return
        if self.playing:
            self.pause()
        else:
            if self.index == len(self.data.frames)-1:
                self.display_frame(0)
            self.playhead = self.data.frames[self.index]["time"]
            self.last_tick = time.monotonic()
            self.playing = True
            self.play_button.setText("Pause")
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def restart(self):
        self.scrub(0)

    def step_forward(self):
        self.scrub(self.index+1)

    def tick(self):
        now = time.monotonic()
        elapsed = min(now-self.last_tick,.2)
        self.last_tick = now
        if not self.playing or not self.data:
            return
        self.playhead = min(self.playhead+elapsed*self.speed.currentData(),self.data.parameters["duration"])
        index = min(int(math.floor((self.playhead+1e-9)/self.data.parameters["dt"])),len(self.data.frames)-1)
        if index != self.index:
            self.display_frame(index)
        if self.index == len(self.data.frames)-1:
            self.pause()

    def open_path(self, path):
        try:
            self.set_run(load_run(path))
        except Exception as error:
            QMessageBox.warning(self,"Invalid recorded run",str(error))

    def open_folder(self):
        path = QFileDialog.getExistingDirectory(self,"Open C++ run folder",str(ROOT/"results"))
        if path:
            self.open_path(path)

    def open_archive(self):
        path,_ = QFileDialog.getOpenFileName(self,"Open saved run",str(ROOT/"results"),"Physarum run archive (*.zip)")
        if path:
            self.open_path(path)

    def save(self):
        if not self.data:
            return
        path,_ = QFileDialog.getSaveFileName(self,"Save complete experiment",str(ROOT/"results/experiment.zip"),"Physarum run archive (*.zip)")
        if path:
            if not path.lower().endswith(".zip"):
                path += ".zip"
            try:
                save_run(self.data,path)
                self.statusBar().showMessage(f"Saved original C++ CSV, configuration and metadata: {path}")
            except OSError as error:
                QMessageBox.critical(self,"Could not save run",str(error))

    def show_notes(self):
        QMessageBox.information(self,"Model and viewer notes",
            "The C++ engine solves pressures and flows, then updates all conductivities with explicit Euler.\n\n"
            "The viewer shows exact recorded states, without interpolation. Playback rate is a display setting, not a model parameter.\n\n"
            "Widths are proportional to D. Conductivities below 1e-10 have no coloured stroke; pale outlines still show every edge. This display convention does not modify the data.\n\n"
            "Use the plot toolbar to zoom, pan and export the current figure. Save run archives to preserve the original CSV, configuration, compiler/Eigen metadata and summary.\n\n"
            "The baseline is a mathematical fixture, not a complete reproduction of Tero et al. (2010). See docs/MATHEMATICAL_MODEL.md.")

    def closeEvent(self,event):
        self.timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.wait(35000)
        event.accept()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",type=Path,help="Open a recorded C++ run directory or ZIP archive.")
    parser.add_argument("--fixture",action="store_true",help="Open the validated four-node viewer instead of London.")
    args = parser.parse_args()
    prepare_platform_plugins()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Physarum Network Viewer")
    app.setApplicationDisplayName("Physarum Network Viewer")
    app.setStyle("Fusion")
    if args.fixture or args.run:
        window = Viewer(auto_run=not args.run)
        if args.run:window.open_path(args.run)
    else:
        try:
            from .spatial_viewer import SpatialViewer
        except ImportError:
            from spatial_viewer import SpatialViewer
        window=SpatialViewer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
