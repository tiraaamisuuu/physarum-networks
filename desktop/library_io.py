"""Cancellable disk checks in child processes, so slow files cannot trap the UI."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time


def run_reader(arguments,cancel,on_message,idle_timeout):
    command=[sys.executable,'-u',str(Path(__file__).with_name('experiment_catalog.py')),*map(str,arguments)]
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    last=time.monotonic();error=None;timed_out=False;buffer=b''
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            while True:
                if cancel.is_set():raise ValueError('Saved experiment check cancelled.')
                if time.monotonic()-last>idle_timeout:timed_out=True;break
                if not selector.select(.1):continue
                chunk=os.read(process.stdout.fileno(),65536)
                if not chunk:break
                last=time.monotonic();buffer+=chunk
                while b'\n' in buffer:
                    line,buffer=buffer.split(b'\n',1);message=json.loads(line)
                    if 'error' in message:error=message['error']
                    on_message(message)
        if timed_out:return False
        if process.wait(timeout=2)!=0:raise ValueError(error or 'Saved experiment check failed.')
        if error:raise ValueError(error)
        return True
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                process.kill()
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:pass
        process.stdout.close();process.stderr.close()


def scan_catalog(catalog,cancel,progress=None,idle_timeout=5):
    rows=[];result=dict(truncated=False)
    def received(message):
        if 'row' in message:
            rows.append(message['row'])
            if progress:progress(message['row'])
        if message.get('complete'):result.update(message)
    complete=run_reader(['--scan',catalog.root],cancel,received,idle_timeout)
    return dict(rows=rows,truncated=result['truncated'],partial=not complete)


def check_record(folder,cancel):
    result={}
    complete=run_reader(['--check',folder],cancel,result.update,120)
    if not complete:raise ValueError('The saved run did not respond in time. Current results are unchanged; try again after the files are available locally.')
    if 'checked' not in result:raise ValueError('No completed record validation was returned.')
    return result['checked']
