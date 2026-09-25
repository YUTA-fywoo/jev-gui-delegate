"""Re-runnable installer. Uses reviewed official wheels and exactly one skill installer."""
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    if sys.platform!="win32" or sys.version_info[:2]!=(3,12):
        raise SystemExit("This lock targets native Windows x64 / Python 3.12.")
    python=ROOT/".venv/Scripts/python.exe"
    if not python.exists():
        subprocess.run([sys.executable,"-m","venv",str(ROOT/".venv")],check=True)
    subprocess.run([str(python),"-m","pip","install","--index-url","https://pypi.org/simple",
        "--only-binary=:all:","--require-hashes","--disable-pip-version-check","-r",str(ROOT/"requirements.lock")],check=True)
    candidates=[Path.home()/".agents/skills/typesafe-ai/SKILL.md",
        Path(os.environ.get("CODEX_HOME") or Path.home()/".codex")/"skills/typesafe-ai/SKILL.md"]
    installed=[p for p in candidates if p.exists()]
    if len(installed)>1: raise SystemExit("Duplicate TypeSafe skills found; preserved for review.")
    if not installed:
        lock=Path.home()/".agents/.skill-lock.json"
        if lock.exists():
            backups=Path(os.environ.get("CODEX_HOME") or Path.home()/".codex")/"backups/jev-bridge"
            backups.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(lock,backups/("skill-lock."+datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".bak"))
        env=dict(os.environ,DISABLE_TELEMETRY="1",npm_config_ignore_scripts="true")
        subprocess.run([shutil.which("npx.cmd") or "npx.cmd","--yes","skills@1.7.0","add","typesafe-ai/skills",
            "--skill","typesafe-ai","--agent","codex","--global","--yes"],env=env,check=True)
    else:
        print("Reusing existing TypeSafe skill:",installed[0])
    subprocess.run([str(python),str(ROOT/"manage.py"),"register"],check=True)
    subprocess.run([str(python),"-m","pip","check"],check=True)
    print("Installation verified. Run health.cmd or verify.cmd; set-key.cmd opens local hidden input.")

if __name__=="__main__":main()
