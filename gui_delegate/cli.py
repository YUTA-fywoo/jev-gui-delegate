import argparse
import asyncio
import json
import shutil
import time
from pathlib import Path
from . import service,storage
from .security import Stop

def main():
    p=argparse.ArgumentParser();p.add_argument("action",choices=["demo","run","resume","cancel","diagnose","stop","clear-stop","cleanup","bind-fallback","restore-clipboard"])
    p.add_argument("value",nargs="?");p.add_argument("--continue-task",action="store_true")
    p.add_argument("--request-json",help="Local Resume JSON file; keeps replacement input values out of command arguments")
    args=p.parse_args()
    if args.action=="demo":
        from .examples import workflow
        result={'status':'needs_browser_session','reason':'OFFICIAL_CHROME_REQUIRES_CURRENT_CODEX_BROWSER_SESSION','adapter':str(service.ROOT/'gui_delegate/chrome_delegate.mjs'),'fixture_server':'python -m gui_delegate.tests.chrome_fixture_server','contract_template':workflow()}
    elif args.action=="run":result=asyncio.run(service.run_task(json.loads(Path(args.value).read_text("utf-8"))))
    elif args.action=="resume":result=asyncio.run(service.resume_task(json.loads(Path(args.request_json).read_text('utf-8')) if args.request_json else {"resume_token":args.value,"continue_task":args.continue_task}))
    elif args.action=="cancel":result=asyncio.run(service.cancel_task({"resume_token":args.value}))
    elif args.action=="diagnose":result=asyncio.run(service.diagnose_task({"resume_token":args.value} if args.value else {}))
    elif args.action=="stop":
        storage.protect_directory(storage.DATA);storage.atomic(storage.DATA/"STOP",b"1");result={"emergency_stop":True}
    elif args.action=="clear-stop":(storage.DATA/"STOP").unlink(missing_ok=True);result={"emergency_stop":False}
    elif args.action=="bind-fallback":
        from .hook import bind
        request=json.loads(Path(args.value).read_text("utf-8"))
        result=bind(**request)
    elif args.action=='restore-clipboard':
        from .clipboard import restore_pending
        result=restore_pending()
    else:
        import re
        removed=0
        if storage.DATA.exists():
            for directory in storage.DATA.iterdir():
                active=(directory/"heartbeat").exists() and time.time()-(directory/"heartbeat").stat().st_mtime<3
                if re.fullmatch(r"[a-f0-9]{32}",directory.name) and directory.is_dir() and not directory.is_symlink() and not active:
                    request=storage.read(directory/"request.dpapi")
                    if time.time()-request["created_at"]>7*86400:
                        if directory.resolve().parent!=storage.DATA.resolve():raise Stop("CLEANUP_PATH_DENIED","blocked")
                        shutil.rmtree(directory);removed+=1
        result={"removed_expired_tasks":removed,"retention_days":7}
    print(json.dumps(result,ensure_ascii=True,indent=2))

if __name__=="__main__":
    import sys
    from pydantic import ValidationError
    try:main()
    except Stop as exc:
        print(json.dumps({'status':exc.status,'error':exc.reason}));sys.exit(1)
    except (ValidationError,ValueError):
        print(json.dumps({'status':'blocked','error':'INVALID_TASK_INPUT'}));sys.exit(1)
    except Exception:
        print(json.dumps({'status':'failed','error':'LOCAL_CLI_FAILURE'}));sys.exit(1)
