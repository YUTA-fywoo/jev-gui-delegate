import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jev_client import ROOT

def browser_probe():
    return {'status':'SKIPPED','driver':'official Chrome session',
            'reason':'Isolated Edge removed. Run chrome_delegate.run_task in the current Codex Browser Use session.'}

def desktop_probe():
    from pywinauto import Application
    from pywinauto.timings import wait_until
    import win32gui
    process=subprocess.Popen([sys.executable,str(ROOT/"tests/gui-window.py")],
        creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    app=None
    try:
        # Windows venv python.exe is a redirector: use the actual window process ID.
        window_pid=int(process.stdout.readline().strip())
        app=Application(backend="uia").connect(process=window_pid,timeout=15)
        window=app.window(title="Jev Integration Test Window")
        window.wait("visible",timeout=15)
        controls=[{"name":c.element_info.name,"role":c.element_info.control_type,"id":c.element_info.automation_id} for c in window.descendants()]
        edit=window.child_window(auto_id="101",control_type="Edit")
        button=window.child_window(auto_id="102",control_type="Button")
        edit.set_edit_text("synthetic UIA draft")
        button.invoke()
        wait_until(5,0.1,lambda:window.child_window(auto_id="103").window_text()=="Saved: synthetic UIA draft")
        # Verify real keyboard/mouse only against this owned test window; restore pointer.
        import win32api
        old_cursor=win32api.GetCursorPos()
        try:
            edit.click_input()
            if win32gui.GetForegroundWindow()!=window.handle:
                raise RuntimeError("TEST_WINDOW_NOT_FOREGROUND")
            edit.type_keys("^aKeyboard probe",with_spaces=True)
            button.click_input()
            wait_until(5,0.1,lambda:window.child_window(auto_id="103").window_text()=="Saved: Keyboard probe")
        finally:
            win32api.SetCursorPos(old_cursor)
        return {"status":"PASS","driver":"pywinauto UIA + Win32 input","process_id":window_pid,
            "structured_controls":controls,"uia_invoke":"PASS","keyboard_mouse":"PASS"}
    finally:
        if app:
            try: app.window(title="Jev Integration Test Window").close()
            except Exception: pass
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)

if __name__=="__main__":
    report={}
    for name,fn in (("browser",browser_probe),("windows_uia",desktop_probe)):
        try: report[name]=fn()
        except Exception as exc: report[name]={"status":"BLOCKED","reason":type(exc).__name__}
    (ROOT/"reports/gui-test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
