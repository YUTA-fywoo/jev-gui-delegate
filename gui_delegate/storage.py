import json
import os
import secrets
import time
from pathlib import Path
import win32crypt
from jev_client import ROOT
from .security import protect_directory,Stop

DATA=ROOT/"gui_delegate/private"

def atomic(path,data):
    path=Path(path);tmp=path.with_suffix(path.suffix+"."+secrets.token_hex(6)+".tmp")
    tmp.write_bytes(data)
    for attempt in range(8):
        try:os.replace(tmp,path);return
        except PermissionError:
            if attempt==7:raise
            time.sleep(0.02)

def save(path,value):
    raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode("utf-8")
    blob=win32crypt.CryptProtectData(raw,None,None,None,None,1)
    atomic(path,blob)

def read(path):
    try:
        return json.loads(win32crypt.CryptUnprotectData(Path(path).read_bytes(),None,None,None,1)[1])
    except Exception:raise Stop("CHECKPOINT_UNAVAILABLE","blocked") from None

def task_directory(token):
    import re
    if not re.fullmatch(r"[a-f0-9]{64}",token):raise Stop("INVALID_RESUME_TOKEN","blocked")
    directory=DATA/token[:32]
    if not directory.is_dir():raise Stop("UNKNOWN_TASK","blocked")
    info=read(directory/"request.dpapi")
    if not secrets.compare_digest(info["token"],token):raise Stop("INVALID_RESUME_TOKEN","blocked")
    return directory

def create(contract):
    protect_directory(DATA)
    token=secrets.token_hex(32);directory=DATA/token[:32];directory.mkdir()
    save(directory/"request.dpapi",{"token":token,"contract":contract.model_dump(),"created_at":time.time()})
    return token,directory

def event(directory,kind,**scalars):
    # No control labels, task text, input values, paths, credentials, or exception strings.
    with (directory/"events.jsonl").open("a",encoding="utf-8") as out:
        out.write(json.dumps({"time":time.time(),"kind":kind,**scalars},ensure_ascii=False)+"\n")
