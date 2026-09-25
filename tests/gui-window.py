"""Owned synthetic Win32 window for UIA and physical input testing."""
import threading
import os
import win32api
import win32con as c
import win32gui as g

children={}
def handler(hwnd,msg,wparam,lparam):
    if msg==c.WM_COMMAND and (wparam & 0xffff)==102:
        g.SetWindowText(children[103],"Saved: "+g.GetWindowText(children[101]))
        return 0
    if msg==c.WM_CLOSE:
        g.DestroyWindow(hwnd)
        return 0
    if msg==c.WM_DESTROY:
        g.PostQuitMessage(0)
        return 0
    return g.DefWindowProc(hwnd,msg,wparam,lparam)

instance=win32api.GetModuleHandle(None)
wc=g.WNDCLASS()
wc.hInstance=instance
wc.lpszClassName="JevOwnedTestWindow"
wc.lpfnWndProc=handler
wc.hbrBackground=c.COLOR_WINDOW+1
g.RegisterClass(wc)
window=g.CreateWindow(wc.lpszClassName,"Jev Integration Test Window",c.WS_OVERLAPPEDWINDOW,
    200,200,540,260,0,0,instance,None)
for ident,kind,label,x,y,width,height,style in [
    (101,"EDIT","",20,30,460,30,c.WS_BORDER|c.ES_AUTOHSCROLL),
    (102,"BUTTON","Save draft",20,85,160,35,c.BS_PUSHBUTTON),
    (103,"STATIC","Not saved",20,140,460,30,0)]:
    children[ident]=g.CreateWindow(kind,label,c.WS_CHILD|c.WS_VISIBLE|c.WS_TABSTOP|style,
        x,y,width,height,window,ident,instance,None)
g.ShowWindow(window,c.SW_SHOW)
g.UpdateWindow(window)
print(os.getpid(),flush=True)
timer=threading.Timer(45,lambda:g.PostMessage(window,c.WM_CLOSE,0,0))
timer.daemon=True
timer.start()
g.PumpMessages()
timer.cancel()
