"""Local experiment labels and discovery, separate from immutable solver records."""
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

EMPTY_NOTE=dict(title='',notes='',favorite=False)


def scenario_key(folder):
    path=Path(folder)/'scenario.json'
    if path.stat().st_size>8_000_000:raise ValueError('Scenario metadata exceeds 8 MB.')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_key(run):
    if not hasattr(run,'_catalog_key'):run._catalog_key=scenario_key(run.folder)
    return run._catalog_key


def validate_note(note):
    if not isinstance(note,dict) or set(note)-{'title','notes','favorite'}:raise ValueError('Invalid experiment note fields.')
    result={**EMPTY_NOTE,**note}
    if not isinstance(result['title'],str) or len(result['title'])>120:raise ValueError('Use a title of at most 120 characters.')
    if not isinstance(result['notes'],str) or len(result['notes'])>8000:raise ValueError('Use notes of at most 8,000 characters.')
    if not isinstance(result['favorite'],bool):raise ValueError('Favorite must be true or false.')
    return dict(title=result['title'].strip(),notes=result['notes'].strip(),favorite=result['favorite'])


class ExperimentCatalog:
    def __init__(self,root):
        self.root=Path(root).resolve();self.path=self.root/'results/experiment_catalog.sqlite3'
    def _connection(self,create=False):
        if not create and not self.path.exists():return None
        if create:self.path.parent.mkdir(parents=True,exist_ok=True)
        con=sqlite3.connect(self.path,timeout=5)
        try:
            version=con.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0,1):raise ValueError('This experiment catalog uses an unsupported version.')
            if create:
                with con:
                    con.execute('CREATE TABLE IF NOT EXISTS notes (identity TEXT PRIMARY KEY,title TEXT NOT NULL,notes TEXT NOT NULL,favorite INTEGER NOT NULL,updated_utc TEXT NOT NULL)')
                    con.execute('CREATE TABLE IF NOT EXISTS locations (folder TEXT PRIMARY KEY)')
                    con.execute('PRAGMA user_version=1')
            elif version!=1:raise ValueError('The experiment catalog has no supported schema.')
            return con
        except Exception:con.close();raise
    def annotations(self):
        con=self._connection()
        if con is None:return {}
        with closing(con):return {key:validate_note(dict(title=title,notes=notes,favorite=bool(favorite))) for key,title,notes,favorite in con.execute('SELECT identity,title,notes,favorite FROM notes')}
    def annotation(self,key):
        con=self._connection()
        if con is None:return dict(EMPTY_NOTE)
        with closing(con):row=con.execute('SELECT title,notes,favorite FROM notes WHERE identity=?',(key,)).fetchone()
        return validate_note(dict(title=row[0],notes=row[1],favorite=bool(row[2]))) if row else dict(EMPTY_NOTE)
    def save(self,key,note):
        if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):raise ValueError('Notes must identify one exact scenario checksum.')
        note=validate_note(note)
        with closing(self._connection(True)) as con,con:
            con.execute('INSERT INTO notes VALUES (?,?,?,?,?) ON CONFLICT(identity) DO UPDATE SET title=excluded.title,notes=excluded.notes,favorite=excluded.favorite,updated_utc=excluded.updated_utc',(key,note['title'],note['notes'],int(note['favorite']),datetime.now(timezone.utc).isoformat()))
        return note
    def remember(self,folder):
        folder=Path(folder).resolve()
        try:location=str(folder.relative_to(self.root))
        except ValueError:location=str(folder)
        with closing(self._connection(True)) as con,con:con.execute('INSERT OR IGNORE INTO locations VALUES (?)',(location,))
    def locations(self):
        con=self._connection()
        if con is None:return []
        with closing(con):return [(self.root/row[0]).resolve() for row in con.execute('SELECT folder FROM locations')]


def discover_experiments(catalog,cancel=None,progress=None):
    """Read bounded metadata only. Full mathematical/checksum validation is deferred."""
    paths=set((catalog.root/'results/mesh_runs').glob('*/scenario.json'))
    paths.update((catalog.root/'results/mesh_sweeps').glob('*/runs/*/scenario.json'))
    paths.update(folder/'scenario.json' for folder in catalog.locations())
    paths=sorted(paths,key=lambda p:(p.parent.name,str(p)),reverse=True);notes=catalog.annotations();rows=[];seen=set()
    for path in paths[:5000]:
        if cancel is not None and cancel.is_set():break
        folder=path.parent.resolve();row=dict(folder=str(folder),id=folder.name,key=None,title=folder.name,map='Unknown',foods=None,saved_utc='',status='Unreadable',detail='',settings={},food_names=[],annotation=dict(EMPTY_NOTE))
        if folder in seen:continue
        seen.add(folder)
        try:
            key=scenario_key(folder);obj=json.loads(path.read_text());scene=obj['scene'];settings=obj['settings']
            if obj.get('model')!='Tero_2010_sigmoid_mesh_v1':continue
            if not isinstance(scene.get('nodes'),list) or not isinstance(scene.get('name'),str) or not isinstance(settings,dict):raise ValueError('Invalid scenario labels or settings.')
            note=notes.get(key,dict(EMPTY_NOTE));foods=[n for n in scene['nodes'] if n.get('kind') in ('station','food')]
            complete=all((folder/relative).is_file() for relative in ('checksums.json','output/D.f64','output/Q.f64','output/P.f64','output/diagnostics.csv','output/metadata.txt'))
            row.update(key=key,title=note['title'] or scene['name'],default_title=scene['name'],map='Sandbox' if scene['geography'].get('coordinate_system')=='local_km' else 'London',foods=len(foods),settings=settings,food_names=[str(n.get('name','')) for n in foods],annotation=note,status='Verify on open' if complete else 'Incomplete',detail='Metadata listing only. Opening rechecks all numerical states, checksums and source provenance.' if complete else 'Required run files are missing. Available files are preserved.')
            try:row['saved_utc']=datetime.strptime(folder.name[:15],'%Y%m%dT%H%M%S').strftime('%Y-%m-%d %H:%M')
            except ValueError:row['saved_utc']='Unknown'
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as error:row['detail']=str(error)
        rows.append(row)
        if progress:progress(row)
    rows.sort(key=lambda r:(r['saved_utc'] if r['saved_utc']!='Unknown' else '',r['id']),reverse=True)
    return dict(rows=rows,truncated=len(paths)>5000)


if __name__=='__main__':
    import sys
    try:
        if sys.argv[1]=='--scan':
            result=discover_experiments(ExperimentCatalog(sys.argv[2]),progress=lambda row:print(json.dumps(dict(row=row)),flush=True))
            print(json.dumps(dict(complete=True,truncated=result['truncated'])),flush=True)
        elif sys.argv[1]=='--check':
            from mesh_data import load_mesh_run
            run=load_mesh_run(sys.argv[2]);print(json.dumps(dict(checked=record_key(run))),flush=True)
        else:raise ValueError('Choose scan or check.')
    except Exception as error:print(json.dumps(dict(error=str(error))),flush=True);sys.exit(1)
