"""Controlled checks and registered MCP; Chrome GUI needs its live Codex session."""
import argparse,asyncio,io,json,unittest
from pathlib import Path
from jev_client import ROOT
def main():
    p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');p.add_argument('--desktop',action='store_true')
    p.add_argument('--report',type=Path,default=ROOT/'gui_delegate/reports/current-verification');args=p.parse_args()
    args.report.mkdir(parents=True,exist_ok=True)
    suites=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromNames(['gui_delegate.tests.'+p.stem for p in sorted((ROOT/'gui_delegate/tests').glob('test_*.py'))]),
        unittest.defaultTestLoader.loadTestsFromNames(['tests.test_failures','tests.test_registration','tests.test_credentials'])])
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suites)
    report={'controlled_checks':{'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},
            'chrome_gui':{'status':'NOT_RUN','reason':'Run chrome_delegate.run_task inside the current official Chrome Browser Use session.'}}
    (args.report/'python-tests.txt').write_text(stream.getvalue(),'utf-8')
    if args.live:
        from .tests.chrome_complete_mcp import main as probe
        report['registered_mcp']=asyncio.run(probe(args.report))
    if args.desktop:
        from .tests.native_probe import probe
        report['native']=probe(args.report/'native.json')
    (args.report/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))
    if not result.wasSuccessful() or any(v.get('status')!='completed' for k,v in report.get('native',{}).items() if k in ('native_cjk','file_dialog','save_dialog')):raise SystemExit(1)
if __name__=='__main__':main()
