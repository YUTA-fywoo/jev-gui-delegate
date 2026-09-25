"""Disposable native buttons. Only synthetic labels and outcome; no real app actions."""
import os,sys,threading,win32api,win32con as c,win32gui as g
controls={};outcome=None
def handle(hwnd,msg,wparam,lparam):
    if msg==c.WM_COMMAND and 200<=wparam&0xffff<212:
        ident=wparam&0xffff
        g.SetWindowText(outcome,g.GetWindowText(controls[ident]));return 0
    if msg==c.WM_CLOSE:g.DestroyWindow(hwnd);return 0
    if msg==c.WM_DESTROY:g.PostQuitMessage(0);return 0
    return g.DefWindowProc(hwnd,msg,wparam,lparam)
instance=win32api.GetModuleHandle(None);wc=g.WNDCLASS();wc.hInstance=instance;wc.lpszClassName='JevCalibrationNative';wc.lpfnWndProc=handle;wc.hbrBackground=c.COLOR_WINDOW+1
g.RegisterClass(wc)
window=g.CreateWindow(wc.lpszClassName,'Jev Synthetic Calibration',c.WS_POPUP|c.WS_BORDER,80,80,750,570,0,0,instance,None)
for i in range(12):controls[200+i]=g.CreateWindow('BUTTON','Synthetic '+str(i),c.WS_CHILD|c.BS_PUSHBUTTON,20,20+i*35,680,30,window,200+i,instance,None)
outcome=g.CreateWindow('STATIC','Pending',c.WS_CHILD|c.WS_VISIBLE|c.SS_NOPREFIX,20,450,680,50,window,103,instance,None)
g.ShowWindow(window,c.SW_SHOWNOACTIVATE);g.UpdateWindow(window)
print(str(os.getpid())+' '+str(window),flush=True)
timer=threading.Timer(1800,lambda:g.PostMessage(window,c.WM_CLOSE,0,0));timer.daemon=True;timer.start()
g.PumpMessages();timer.cancel()
