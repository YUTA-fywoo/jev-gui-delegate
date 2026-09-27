"""Prepare only the fixed Chrome worker; never return environment values."""
import json
import os
import runpy
from pathlib import Path

SYSTEM_KEYS=('PATH','SYSTEMROOT','SYSTEMDRIVE','WINDIR','PROGRAMFILES','PROGRAMFILES(X86)',
    'PROGRAMW6432','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA')

def prepare_environment(source,environ):
    for key in SYSTEM_KEYS:
        if isinstance(source.get(key),str):environ.setdefault(key,source[key])
    environ['PYTHONUTF8']='1'

def main():
    config=Path(__file__).with_name('chrome-runtime.json')
    source=json.loads(config.read_text('utf-8')).get('env',{}) if config.exists() else {}
    prepare_environment(source,os.environ)
    runpy.run_module('gui_delegate.chrome_worker',run_name='__main__')

if __name__=='__main__':main()
