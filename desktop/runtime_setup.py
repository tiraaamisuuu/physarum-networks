"""Prepare a reusable app runtime outside the project; uses only the standard library."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parents[1]


def runtime_directory():
    if sys.platform=='darwin':base=Path.home()/'Library/Caches/Physarum'
    elif os.name=='nt':base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'Physarum/Cache'
    else:base=Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'physarum'
    return base/f'python-{sys.version_info.major}.{sys.version_info.minor}'


def requirements_key(root=ROOT):
    data=sys.version.encode()+b'\n'
    for name in ('desktop/requirements.txt','analysis/requirements.txt'):data+=name.encode()+b'\n'+(root/name).read_bytes()
    return hashlib.sha256(data).hexdigest()


def probe(python,root):
    # Check distributions and required plugin files without starting a GUI.
    code='''import importlib.metadata as m,importlib.util as u,pathlib,sys,json
req=json.loads(sys.argv[1])
assert all(m.version(k)==v for k,v in req.items())
base=pathlib.Path(u.find_spec('PySide6').origin).parent/'Qt/plugins/platforms'
names=('libqcocoa.dylib','libqoffscreen.dylib') if sys.platform=='darwin' else ('qwindows.dll','qoffscreen.dll') if sys.platform=='win32' else ('libqxcb.so','libqoffscreen.so')
assert all((base/n).is_file() for n in names)
'''
    requirements={}
    for path in (root/'desktop/requirements.txt',root/'analysis/requirements.txt'):
        for line in path.read_text().splitlines():
            line=line.strip()
            if line and not line.startswith('#'):
                name,version=line.split('==');requirements[name]=version
    try:return subprocess.run([str(python),'-c',code,json.dumps(requirements)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20).returncode==0
    except (OSError,subprocess.TimeoutExpired):return False


def ensure_runtime(root=ROOT,directory=None):
    if not (3,12)<=sys.version_info[:2]<(3,15):raise ValueError('The pinned app dependencies require Python 3.12–3.14.')
    root=Path(root);directory=Path(directory or runtime_directory());directory.mkdir(parents=True,exist_ok=True)
    python=directory/('Scripts/python.exe' if os.name=='nt' else 'bin/python');marker=directory/'ready.json';key=requirements_key(root)
    with (directory/'setup.lock').open('a') as lock:
        if os.name!='nt':
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX)
        try:ready=json.loads(marker.read_text()).get('requirements_sha256')==key
        except (OSError,ValueError,AttributeError):ready=False
        if ready and python.exists() and probe(python,root):return python
        if not python.exists():venv.EnvBuilder(with_pip=True,symlinks=os.name!='nt').create(directory)
        command=[str(python),'-m','pip','install','--disable-pip-version-check','--force-reinstall','-r',str(root/'desktop/requirements.txt'),'-r',str(root/'analysis/requirements.txt')]
        subprocess.run(command,check=True,stdout=sys.stderr,stderr=sys.stderr)
        if not probe(python,root):raise ValueError('App runtime preparation did not supply the required packages and Qt plugins.')
        temporary=directory/'ready.json.tmp';temporary.write_text(json.dumps(dict(schema_version=1,requirements_sha256=key))+'\n');temporary.replace(marker)
        return python


if __name__=='__main__':
    try:print(ensure_runtime())
    except Exception as error:print('Could not prepare the Physarum runtime: '+str(error),file=sys.stderr);sys.exit(1)
