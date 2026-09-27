"""Re-runnable installer. Uses reviewed official wheels and exactly one skill installer."""
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def update_install_manifest(home,python):
    manifest=home/'jev-integration.json'
    data=json.loads(manifest.read_text('utf-8')) if manifest.exists() else {}
    data.setdefault('schema_version',1)
    data.update(project_path=str(ROOT),registration='registered',mcp_name='jev-bridge',new_conversation_required=True)
    data.setdefault('runtime',{})['python_executable']=str(python)
    data.setdefault('tests',{}).setdefault('real_jev','NOT_RUN')
    content=json.dumps(data,ensure_ascii=False,indent=2)
    if manifest.exists():
        if manifest.read_text('utf-8')==content:return
        backups=home/'backups/jev-bridge';backups.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(manifest,backups/('jev-integration.json.'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.bak'))
    home.mkdir(parents=True,exist_ok=True)
    manifest.write_text(content,encoding='utf-8')

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
    installed=list(dict.fromkeys(p.resolve() for p in candidates if p.exists()))
    if len(installed)>1: raise SystemExit("Duplicate TypeSafe skills found; preserved for review.")
    if not installed:
        lock=Path.home()/".agents/.skill-lock.json"
        if lock.exists():
            backups=Path(os.environ.get("CODEX_HOME") or Path.home()/".codex")/"backups/jev-bridge"
            backups.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(lock,backups/("skill-lock."+datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".bak"))
        env=dict(os.environ,DISABLE_TELEMETRY="1",npm_config_ignore_scripts="true")
        npx=shutil.which('npx.cmd')
        bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/npx.cmd'
        if not npx and bundled.exists():npx=str(bundled)
        if not npx:raise SystemExit('Node.js with npx is required to install the TypeSafe skill.')
        subprocess.run([npx,"--yes","skills@1.7.0","add","typesafe-ai/skills",
            "--skill","typesafe-ai","--agent","codex","--global","--yes"],env=env,check=True)
    else:
        print("Reusing existing TypeSafe skill:",installed[0])
    subprocess.run([str(python),str(ROOT/"manage.py"),"register"],check=True)
    subprocess.run([str(python),"-m","pip","check"],check=True)
    subprocess.run([str(python),str(ROOT/"scripts/setup-runtime.py")],check=True)
    home=Path(os.environ.get("CODEX_HOME") or Path.home()/".codex").resolve()
    update_install_manifest(home,python)
    print("Installation verified. Run health.cmd or verify.cmd; set-key.cmd opens local hidden input.")

if __name__=="__main__":main()
