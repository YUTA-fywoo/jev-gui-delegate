"""Generate a local, untracked Chrome worker environment without copying secrets."""
import json
import os
from pathlib import Path

KEYS = ['PATH','SYSTEMROOT','SYSTEMDRIVE','WINDIR','PROGRAMFILES','PROGRAMFILES(X86)',
        'PROGRAMW6432','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA']
target = Path(__file__).resolve().parents[1] / 'gui_delegate/chrome-runtime.json'
target.write_text(json.dumps({'env':{key:os.environ[key] for key in KEYS if key in os.environ}},indent=2),encoding='utf-8')
print('Local Chrome worker environment created. This file must stay untracked.')
