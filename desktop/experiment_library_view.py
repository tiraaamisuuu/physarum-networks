"""Native library: metadata discovery is cheap; opening validates full records."""
from pathlib import Path
import threading
from PySide6.QtCore import QThread,Signal,Qt,QTimer,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QLineEdit,QPlainTextEdit,QCheckBox,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QSplitter,QFileDialog)
try:
    from .experiment_catalog import discover_experiments,record_key
    from .library_io import scan_catalog,check_record
    from .mesh_data import load_mesh_run
except ImportError:
    from experiment_catalog import discover_experiments,record_key
    from library_io import scan_catalog,check_record
    from mesh_data import load_mesh_run


class LibraryWorker(QThread):
    completed=Signal(object);failed=Signal(str);progress=Signal(object)
    def __init__(self,task,parent):super().__init__(parent);self.task=task;self.cancel=threading.Event()
    def run(self):
        try:
            result=self.task(self.cancel)
            if not self.cancel.is_set():self.completed.emit(result)
        except Exception as error:
            if not self.cancel.is_set():self.failed.emit(str(error))


class ExperimentLibrary(QWidget):
    def __init__(self,owner,catalog):
        super().__init__();self.owner=owner;self.catalog=catalog;self.worker=None;self.kind=None;self.rows=[];self.visible_rows=[];self.selected=None;self.dirty=True;self.revision=0;self.scan_revision=0;self.note_dirty=False;self.filling=False;self.pending_open=None
        layout=QVBoxLayout(self);intro=QLabel('Find saved London and sandbox experiments. Opening a result rechecks every numerical state, checksum and source record. Names, notes and favourites live in a separate local catalog.');intro.setWordWrap(True);layout.addWidget(intro)
        filters=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Search names, notes, food sites or run IDs…');filters.addWidget(self.search,1);self.maps=QComboBox();self.maps.addItems(['All maps','London','Sandbox']);filters.addWidget(self.maps);self.favorites=QCheckBox('Favourites');filters.addWidget(self.favorites);refresh=QPushButton('Refresh');refresh.clicked.connect(self.refresh);filters.addWidget(refresh);layout.addLayout(filters)
        bar=QHBoxLayout();self.open_button=QPushButton('Open selected');self.open_button.clicked.connect(lambda:self.open_selected('open'));bar.addWidget(self.open_button);self.reference_button=QPushButton('Use as comparison reference');self.reference_button.clicked.connect(lambda:self.open_selected('reference'));bar.addWidget(self.reference_button);browse=QPushButton('Add run folder…');browse.clicked.connect(self.browse);bar.addWidget(browse);folder=QPushButton('Open selected files');folder.clicked.connect(self.open_files);bar.addWidget(folder);self.cancel_button=QPushButton('Cancel check');self.cancel_button.clicked.connect(self.cancel);self.cancel_button.setVisible(False);bar.addWidget(self.cancel_button);bar.addStretch();layout.addLayout(bar)
        self.status=QLabel('Open this tab to discover saved experiments.');self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        split=QSplitter(Qt.Orientation.Horizontal);layout.addWidget(split,1);self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['★','Experiment','Map','Foods','Recorded UTC','Record']);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch);split.addWidget(self.table)
        details=QWidget();details.setMinimumWidth(250);details.setMaximumWidth(400);dl=QVBoxLayout(details);self.identity=QLabel('Select an experiment.');self.identity.setWordWrap(True);self.identity.setTextFormat(Qt.TextFormat.PlainText);dl.addWidget(self.identity)
        form=QFormLayout();self.title=QLineEdit();self.title.setMaxLength(120);self.title.setPlaceholderText('Give this experiment a useful name');form.addRow('Name',self.title);self.favorite=QCheckBox('Favourite');form.addRow(self.favorite);dl.addLayout(form);dl.addWidget(QLabel('Experiment notes'));self.notes=QPlainTextEdit();self.notes.setPlaceholderText('What changed? What did you observe? What should you compare next?');dl.addWidget(self.notes,1);self.save=QPushButton('Save name and notes');self.save.clicked.connect(lambda:self.save_notes());dl.addWidget(self.save);discard=QPushButton('Discard unsaved note edits');discard.clicked.connect(lambda:self.fill_details(self.selected));dl.addWidget(discard);self.note_status=QLabel('User annotations are separate from model evidence.');self.note_status.setWordWrap(True);self.note_status.setTextFormat(Qt.TextFormat.PlainText);dl.addWidget(self.note_status);split.addWidget(details);split.setSizes([700,320])
        self.search.textChanged.connect(self.filter_rows);self.maps.currentTextChanged.connect(self.filter_rows);self.favorites.toggled.connect(self.filter_rows);self.table.itemSelectionChanged.connect(self.selection_changed);self.table.cellDoubleClicked.connect(lambda *_:self.open_selected('open'))
        for signal in (self.title.textChanged,self.notes.textChanged,self.favorite.toggled):signal.connect(self.note_edited)
        self.set_details_enabled(False);self.buttons()
    def running(self):return self.worker is not None
    def loading(self):return self.worker is not None and self.kind in ('open','reference')
    def showEvent(self,event):
        super().showEvent(event)
        if self.dirty:QTimer.singleShot(0,self.refresh)
    def record_changed(self):
        self.revision+=1;self.dirty=True
        if self.isVisible() and not self.running():QTimer.singleShot(0,self.refresh)
    def start(self,kind,task,callback):
        if self.running() or self.owner.closing:return
        self.kind=kind;self.worker=LibraryWorker(task,self);self.worker.completed.connect(callback);self.worker.failed.connect(self.failed);self.worker.progress.connect(self.scanning_row);self.worker.finished.connect(self.finished);self.cancel_button.setText('Stop scanning' if kind=='scan' else 'Cancel check');self.cancel_button.setVisible(True);self.set_details_enabled(False);self.buttons();self.owner.draft();self.worker.start()
    def refresh(self):
        if self.running() or self.owner.closing:return
        if self.note_dirty and not self.save_notes():return
        self.scan_revision=self.revision;self.rows=[];self.status.setText('Reading saved experiment metadata…');self.start('scan',lambda cancel:scan_catalog(self.catalog,cancel,lambda row:self.worker.progress.emit(row)),self.scanned)
    def scanning_row(self,row):
        if self.kind!='scan' or self.owner.closing:return
        self.rows.append(row)
        if len(self.rows)==1 or len(self.rows)%5==0:self.filter_rows();self.status.setText(f'{len(self.rows)} experiment folders found. You can open a result now or stop scanning.')
    def scanned(self,result):
        self.rows=result['rows'];self.dirty=self.scan_revision!=self.revision;self.filter_rows();self.status.setText(f"{len(self.rows)} saved experiment folders · metadata listing; full validation happens on opening."+(' Some files did not respond; showing the records read so far. Refresh to retry, or add a specific folder.' if result.get('partial') else '')+(' Showing at most 5,000 folders.' if result['truncated'] else ''))
    def filter_rows(self,*_):
        if self.note_dirty and not self.save_notes(rebuild=False):return
        keep=self.selected['folder'] if self.selected else None;query=self.search.text().casefold().strip();scope=self.maps.currentText();favorite=self.favorites.isChecked()
        rows=[r for r in self.rows if (scope=='All maps' or r['map']==scope) and (not favorite or r['annotation']['favorite']) and query in ' '.join([r['title'],r['id'],r['annotation']['notes'],*r['food_names']]).casefold()]
        self.visible_rows=rows;self.filling=True;self.table.setRowCount(len(rows));selected=-1
        for i,row in enumerate(rows):
            for j,value in enumerate(('★' if row['annotation']['favorite'] else '',row['title'],row['map'],str(row['foods']) if row['foods'] is not None else '—',row['saved_utc'],row['status'])):
                item=QTableWidgetItem(value);item.setToolTip(row['detail']);self.table.setItem(i,j,item)
            if row['folder']==keep:selected=i
        self.table.clearSelection();self.filling=False;self.selected=None
        if selected>=0:self.table.selectRow(selected);self.fill_details(rows[selected])
        elif rows:self.table.selectRow(0);self.fill_details(rows[0])
        else:self.fill_details(None)
        self.buttons()
    def selection_changed(self):
        if self.filling:return
        if self.note_dirty and not self.save_notes(rebuild=False):
            self.filling=True
            for i,row in enumerate(self.visible_rows):
                if self.selected and row['folder']==self.selected['folder']:self.table.selectRow(i);break
            self.filling=False;return
        row=self.table.currentRow();self.fill_details(self.visible_rows[row] if 0<=row<len(self.visible_rows) else None);self.buttons()
    def fill_details(self,row):
        self.filling=True;self.selected=row;self.note_dirty=False;note=row['annotation'] if row else dict(title='',notes='',favorite=False);self.title.setText(note['title']);self.title.setCursorPosition(0);self.notes.setPlainText(note['notes']);self.favorite.setChecked(note['favorite']);self.set_details_enabled(row is not None and row['key'] is not None and not self.running())
        if row:
            settings=row['settings'];self.identity.setText(f"{row['title']}\n{row['id']}\n{row['map']} · {row['foods']} food sites\nγ {settings.get('gamma','—')} · I₀ {settings.get('current','—')} · seed {settings.get('seed','—')}\n{row['status']}\n{row['detail']}")
        else:self.identity.setText('No matching experiments. Compute a run or add a complete run folder.')
        self.note_status.setText('Names and notes never overwrite the numerical record.');self.filling=False
    def set_details_enabled(self,enabled):
        for widget in (self.title,self.notes,self.favorite,self.save):widget.setEnabled(enabled)
    def note_edited(self,*_):
        if not self.filling and self.selected:self.note_dirty=True;self.note_status.setText('Unsaved annotations · saved when you switch selection or press Save.')
    def save_notes(self,rebuild=True):
        if not self.selected or not self.selected['key']:return True
        try:
            note=self.catalog.save(self.selected['key'],dict(title=self.title.text(),notes=self.notes.toPlainText(),favorite=self.favorite.isChecked()));key=self.selected['key'];self.note_dirty=False
            for row in self.rows:
                if row['key']==key:row['annotation']=note;row['title']=note['title'] or row.get('default_title',row['title'])
            self.owner.annotations_changed()
            if rebuild:self.filter_rows()
            self.note_status.setText('Name and notes saved locally. Numerical files are unchanged.')
            return True
        except Exception as error:self.note_status.setText(str(error));return False
    def buttons(self):
        valid=self.selected is not None and self.selected['status']=='Verify on open';enabled=valid and (not self.running() or self.kind=='scan');self.open_button.setEnabled(enabled);self.reference_button.setEnabled(enabled)
    def open_selected(self,kind):
        if self.selected:self.open_path(self.selected['folder'],kind)
    def browse(self):
        folder=QFileDialog.getExistingDirectory(self,'Add a complete tube experiment',str(self.catalog.root/'results/mesh_runs'))
        if folder:self.open_path(folder,'open',True)
    def open_path(self,folder,kind='open',remember=False):
        if self.running():
            if self.kind=='scan':self.pending_open=(folder,kind,remember);self.cancel()
            return
        if self.note_dirty and not self.save_notes():return
        if (self.owner.worker and self.owner.worker.isRunning()) or self.owner.sweep_panel.running():self.status.setText('Finish or cancel the active experiment before opening a saved result.');return
        folder=Path(folder);self.status.setText('Checking all saved states, inputs, checksums and source provenance…')
        def load(cancel):
            checked=check_record(folder,cancel)
            if cancel.is_set():raise ValueError('Record check cancelled.')
            run=load_mesh_run(folder)
            if record_key(run)!=checked:raise ValueError('The scenario changed while it was being checked. Refresh and reopen it.')
            return run
        def accept(run):
            if self.owner.closing:return
            if remember:
                try:self.catalog.remember(folder)
                except Exception as error:self.status.setText('Record checked, but its location could not be remembered: '+str(error))
            if kind=='reference':self.owner.pin_reference(run)
            else:self.owner.install_record(run)
            self.record_changed()
        self.start(kind,load,accept)
    def open_files(self):
        if self.selected:QDesktopServices.openUrl(QUrl.fromLocalFile(self.selected['folder']))
    def cancel(self):
        if self.worker:self.worker.cancel.set();self.dirty=False;self.status.setText('Cancelling. The current record and draft remain available. A running check will finish before closing.')
    def failed(self,error):self.dirty=False;self.status.setText('Could not open experiment: '+error)
    def finished(self):
        worker=self.worker;self.worker=None;self.kind=None
        if worker:worker.deleteLater()
        self.cancel_button.setVisible(False);self.set_details_enabled(self.selected is not None and self.selected['key'] is not None);self.buttons();self.owner.draft()
        if self.owner.closing:QTimer.singleShot(0,self.owner.close)
        elif self.pending_open:
            pending=self.pending_open;self.pending_open=None;self.open_path(*pending)
        elif self.dirty and self.isVisible():QTimer.singleShot(0,self.refresh)
