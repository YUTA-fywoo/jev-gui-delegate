"""Remove only owned registration; optional skill/credential removal is explicit."""
import argparse
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from manage import ROOT,rollback

parser=argparse.ArgumentParser()
parser.add_argument("--delete-credential",action="store_true")
parser.add_argument("--remove-skill",action="store_true")
args=parser.parse_args()
skill=Path.home()/".agents/skills/typesafe-ai/SKILL.md"
if args.remove_skill and skill.exists():
    official=ROOT/"docs/official-typesafe-SKILL.md"
    if not official.exists() or skill.read_text("utf-8").strip()!=official.read_text("utf-8").strip():
        raise SystemExit("Official skill has changed; preserving it for review.")
rollback(args.delete_credential)
if args.remove_skill and skill.exists():
    subprocess.run([shutil.which("npx.cmd") or "npx.cmd","--yes","skills@1.7.0","remove","typesafe-ai",
        "--agent","codex","--global","--yes"],
        env=dict(os.environ,DISABLE_TELEMETRY="1",npm_config_ignore_scripts="true"),check=True)
print("Project files retained for inspection/reinstallation; no unrelated dependency removed.")
