"""Package current maintained source without rebuilding historical releases."""
import hashlib,json,zipfile
from pathlib import Path
from jev_client import ROOT
def package(destination=None):
    destination=Path(destination or ROOT.parent/'jev-gui-current-source.zip')
    excluded={'.venv','node_modules','__pycache__','private','reports','logs','.git','docs'}
    suffixes={'.py','.mjs','.js','.json','.md','.cmd','.yaml','.toml','.lock','.html','.txt'}
    files=[p for p in ROOT.rglob('*') if p.is_file() and p.suffix in suffixes and not any(x in excluded for x in p.relative_to(ROOT).parts) and '.backup-' not in p.name]
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
        evidence=ROOT/'gui_delegate/reports/strict-routing-20260923'
        for name in ('REPORT.md','verification-final.json','rollback-test.json','mcp.json','discovery.json','actual-hook.json','chrome-live.json','resume-live.json','javascript-tests.json','python-tests.txt'):
            p=evidence/name
            if p.exists():z.write(p,p.relative_to(ROOT).as_posix())
        current=ROOT/'gui_delegate/reports/tab-cleanup-20260924'
        for name in ('REPORT.md','live-result.json','cleanup-tests.json','adapter-tests.json','protocol-test.json','python-tests.txt','mcp-test.json'):
            p=current/name
            if p.exists():z.write(p,p.relative_to(ROOT).as_posix())
        audit=ROOT/'gui_delegate/reports/delegation-audit-20260924'
        for name in ('REPORT.md','verification.json','before-metrics.json','after-metrics.json','chrome-live.json','mcp.json','discovery.json','presentation-test.json','rollback-test.json','restore_release.py','release-files.json','before.zip','after.zip'):
            p=audit/name
            if p.exists():z.write(p,p.relative_to(ROOT).as_posix())
    return {'archive':str(destination),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'source_files':len(files),
            'private_tasks_credentials_and_historical_backups_included':False}
def main():print(json.dumps(package(),ensure_ascii=True))
if __name__=='__main__':main()
