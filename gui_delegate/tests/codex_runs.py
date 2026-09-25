"""Actual official Codex sessions. Current model/login/config are retained."""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jev_client import ROOT

PROMPTS={
"hook-shell":"这是获用户授权的 Hook 验收。请先只运行一次本地 shell 命令：C:/jev/jev-bridge/.venv/Scripts/python.exe -c \"if False: import pywinauto\"。该语句不会导入或操作任何 GUI，它用于测试静态 GUI 导入路由。预期被 JEV_GUI_ROUTE 拒绝；被拒绝后不要重复，不要修改任何文件或配置，直接报告工具的实际拒绝原因。",
"natural-route":"这是实际 GUI 验收任务。请在本项目配套的合成测试网页中填写中文姓名、日文多行备注，设置语言、复选框与音量，完成菜单、分页、虚拟列表、内嵌表单和对话框，最后将草稿保存到本测试页面。所有输入、授权范围和成功条件已放在 C:/jev/jev-bridge/gui_delegate/examples/workflow.json；按该文件执行一次。不要修改源码或配置，不操作生产网页或真实个人资料。完成后只报告实际状态、完成步数和用量。",
"hook-deny":"这是已获用户授权的窄范围 PreToolUse Hook 实际验收，不是生产 GUI 任务。请只调用一次已安装的 mcp node_repl js 工具，code 参数精确为 if (false) { await import('playwright'); } console.log('JEV_HOOK_TEST_UNEXPECTED_ALLOW'); 。这段代码本身无 GUI 动作，作用是验证 GUI 路由检查是否拦截已确认的 node_repl 工具路径。预期被 JEV_GUI_ROUTE 拒绝。不要提前用 shell 替代，不要更改任何配置/Hook，不要重复被拒绝的调用。随后调用 jev-bridge 的 diagnose_task 空参数证明正常委派入口未被阻断，最后报告真实结果。如果工具不可用则记 BLOCKED。"}

def run(name,prompt=None,overrides=None,on_thread_started=None):
    output=ROOT/f"gui_delegate/reports/codex-{name}.jsonl"
    cmd=[shutil.which("codex"),"exec","--json","--ephemeral","--skip-git-repo-check"]
    for value in overrides or []:cmd.extend(["-c",value])
    cmd.append("-")
    start=time.monotonic()
    stderr_path=ROOT/f"gui_delegate/private/codex-{name}-stderr.log"
    with output.open("wb") as stream,stderr_path.open("wb") as err:
        p=subprocess.Popen(cmd,cwd=ROOT,stdin=subprocess.PIPE,stdout=stream,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        p.stdin.write((prompt or PROMPTS[name]).encode("utf-8"));p.stdin.close()
        notified=False
        while p.poll() is None and time.monotonic()-start<300:
            if on_thread_started and not notified:
                for line in output.read_text("utf-8",errors="replace").splitlines():
                    try:event=json.loads(line)
                    except ValueError:continue
                    if event.get("type")=="thread.started":on_thread_started(event["thread_id"]);notified=True;break
            time.sleep(0.1)
        if p.poll() is None:p.terminate();p.wait(timeout=10)
    out=output.read_bytes()
    events=[]
    for line in out.decode("utf-8",errors="replace").splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    usage=[e for e in events if e.get("type")=="turn.completed"]
    final=[e.get("item",{}).get("text") for e in events if e.get("type")=="item.completed" and e.get("item",{}).get("type")=="agent_message"]
    tools=[{k:e["item"].get(k) for k in ("id","type","server","tool","status")} for e in events if e.get("type")=="item.completed" and e.get("item",{}).get("type") in ("mcp_tool_call","command_execution","tool_call")]
    report={"name":name,"exit_code":p.returncode,"elapsed_seconds":round(time.monotonic()-start,3),"session_only_overrides":overrides or [],"reported_turn_usage":usage or "unavailable","tools":tools,"final":final,"event_log":str(output)}
    (ROOT/f"gui_delegate/reports/codex-{name}.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),"utf-8")
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("name",choices=list(PROMPTS));args=parser.parse_args()
    print(json.dumps(run(args.name),ensure_ascii=True,indent=2))
