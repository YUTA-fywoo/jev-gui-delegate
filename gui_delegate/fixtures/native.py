"""Owned disposable native UI, with a real Windows common file dialog."""
import os
import threading
import sys
import win32api
import win32con as c
import win32gui as g
from pathlib import Path

controls={}
previous_foreground=g.GetForegroundWindow()
def handler(hwnd,msg,wparam,lparam):
    if msg==c.WM_APP+1:
        try:
            g.SetForegroundWindow(hwnd)
            if g.GetForegroundWindow()==hwnd:
                win32api.keybd_event(0x87,0,0,0);win32api.keybd_event(0x87,0,c.KEYEVENTF_KEYUP,0)
                print('INJECTED_OWNED_F24',flush=True)
        except Exception:print('INPUT_INJECTION_BLOCKED',flush=True)
        return 0
    if msg==c.WM_COMMAND:
        ident=wparam&0xffff
        if ident==102:
            g.SetWindowText(controls[103],"保存済み: "+g.GetWindowText(controls[101]));return 0
        if ident==104:
            try:
                filename,_,_=g.GetOpenFileNameW(hwndOwner=hwnd,Title="Jev Test Open File",InitialDir=str(Path(__file__).parent),
                    Filter="Text files\0*.txt\0All files\0*.*\0",Flags=c.OFN_FILEMUSTEXIST|c.OFN_PATHMUSTEXIST)
                g.SetWindowText(controls[105],filename)
            except Exception:pass
            return 0
        if ident==106:
            try:
                reports=Path(__file__).resolve().parents[1]/'reports'
                filename,_,_=g.GetSaveFileNameW(hwndOwner=hwnd,Title='Jev Test Save File',InitialDir=str(reports),File='native-saved.txt',
                    Filter='Text files\0*.txt\0',DefExt='txt',Flags=c.OFN_PATHMUSTEXIST|c.OFN_OVERWRITEPROMPT)
                output=Path(filename).resolve()
                if output.is_relative_to(reports.resolve()):
                    with output.open('x',encoding='utf-8') as out:out.write('Synthetic native save fixture.')
                    g.SetWindowText(controls[105],str(output))
            except Exception:pass
            return 0
    if msg==c.WM_CLOSE:
        if g.GetForegroundWindow()==hwnd and g.IsWindow(previous_foreground):
            try:g.SetForegroundWindow(previous_foreground)
            except Exception:pass
        g.DestroyWindow(hwnd);return 0
    if msg==c.WM_DESTROY:g.PostQuitMessage(0);return 0
    return g.DefWindowProc(hwnd,msg,wparam,lparam)

instance=win32api.GetModuleHandle(None);wc=g.WNDCLASS();wc.hInstance=instance
wc.lpszClassName="JevDelegateNativeFixture";wc.lpfnWndProc=handler;wc.hbrBackground=c.COLOR_WINDOW+1
g.RegisterClass(wc)
window=g.CreateWindow(wc.lpszClassName,"Jev Delegate Native Fixture",c.WS_OVERLAPPEDWINDOW,180,180,760,560,0,0,instance,None)
for ident,kind,label,x,y,width,height,style in [
    (101,"EDIT","",20,20,700,90,c.WS_BORDER|c.ES_MULTILINE|c.ES_AUTOVSCROLL),
    (102,"BUTTON","保存",20,130,160,35,c.BS_PUSHBUTTON),
    (103,"STATIC","未保存",20,180,700,60,c.SS_NOPREFIX),
    (104,"BUTTON","Open fixture file",20,260,200,35,c.BS_PUSHBUTTON),
    (106,"BUTTON","Save fixture file",280,260,200,35,c.BS_PUSHBUTTON),
    (105,"STATIC","No file",20,310,700,35,c.SS_NOPREFIX)]:
    controls[ident]=g.CreateWindow(kind,label,c.WS_CHILD|c.WS_VISIBLE|c.WS_TABSTOP|style,x,y,width,height,window,ident,instance,None)
import ctypes
ctypes.windll.comctl32.InitCommonControls()
controls[110]=g.CreateWindow('msctls_trackbar32','Fixture slider',c.WS_CHILD|c.WS_VISIBLE|c.WS_TABSTOP,20,360,250,40,window,110,instance,None)
g.SendMessage(controls[110],0x406,1,10<<16)
controls[111]=g.CreateWindow('LISTBOX','Fixture list',c.WS_CHILD|c.WS_VISIBLE|c.WS_BORDER|c.WS_VSCROLL,300,360,380,120,window,111,instance,None)
for i in range(40):g.SendMessage(controls[111],0x180,0,'Synthetic item '+str(i))
g.ShowWindow(window,c.SW_SHOWNOACTIVATE);g.UpdateWindow(window)
print(str(os.getpid())+" "+str(window),flush=True)
if '--simulate-user-input' in sys.argv:
    injection=threading.Timer(3,lambda:g.PostMessage(window,c.WM_APP+1,0,0));injection.daemon=True;injection.start()
timer=threading.Timer(120,lambda:g.PostMessage(window,c.WM_CLOSE,0,0));timer.daemon=True;timer.start()
g.PumpMessages();timer.cancel()
