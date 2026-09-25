import os
import time
from .schema import Control,Observation
from .security import Stop,digest

def observation(seq,location,controls,tab_count=1):
    values=[c.model_dump() for c in controls]
    return Observation(sequence=seq,observed_at=time.monotonic(),fingerprint=digest([location,values,tab_count]),location=location,controls=controls,tab_count=tab_count)

class Windows:
    supported_ops={"read","wait","fill","click","select","check","uncheck","copy","paste","scroll","range"}
    def __init__(self,contract):
        self.contract=contract;self.seq=0;self.handles={}
    def identity(self):
        import win32gui,win32process,win32api,win32con
        t=self.contract.target
        if not win32gui.IsWindow(t.hwnd):raise Stop("WINDOW_CLOSED")
        _,pid=win32process.GetWindowThreadProcessId(t.hwnd)
        if pid!=t.process_id or win32gui.GetWindowText(t.hwnd)!=t.window_title:raise Stop("WINDOW_IDENTITY_CHANGED","blocked")
        h=win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION,False,pid)
        try:
            import ctypes
            size=ctypes.c_ulong(32768);buf=ctypes.create_unicode_buffer(size.value)
            if not ctypes.windll.kernel32.QueryFullProcessImageNameW(int(h),0,buf,ctypes.byref(size)):raise Stop("PROCESS_IDENTITY_UNAVAILABLE")
            if os.path.normcase(buf.value)!=os.path.normcase(t.executable):raise Stop("PROGRAM_DENIED","blocked")
        finally:h.Close()
        if not win32gui.IsWindowVisible(t.hwnd):raise Stop("WINDOW_NOT_VISIBLE")
    def open(self):
        from pywinauto import Application
        self.identity()
        self.app=Application(backend="uia").connect(process=self.contract.target.process_id,timeout=5)
        self.window=self.app.window(handle=self.contract.target.hwnd).wrapper_object()
    def observe(self):
        import win32gui
        # A common dialog can destroy a child HWND while its UIA descendants
        # are being read. Discard that entire snapshot and enumerate afresh.
        # This retries observation only, never an already dispatched action.
        for attempt in range(3):
            try:return self._observe()
            except win32gui.error as exc:
                if exc.winerror!=1400:raise
                if attempt==2:raise Stop('STATE_KEEPS_CHANGING') from None
                time.sleep(.01)
    def _observe(self):
        self.identity();controls=[];handles={}
        descendants=self.window.descendants()
        import win32gui
        for window in self.app.windows():
            if window.handle!=self.window.handle and win32gui.GetWindow(window.handle,4)==self.window.handle:
                descendants.extend(window.descendants())
        if len(descendants)>600:raise Stop("OBSERVATION_TOO_LARGE_USE_SCOPED_ADAPTER")
        for i,w in enumerate(descendants):
            info=w.element_info
            ident=str(info.runtime_id)
            if ident in handles:continue
            try:password=bool(info.element.CurrentIsPassword)
            except Exception:password=True if info.control_type=="Edit" else False
            value=None;checked=None
            if info.control_type=="Edit" and not password:
                try:value=w.get_value()
                except Exception:value=w.window_text()
            if info.control_type in ('Slider','Spinner','ProgressBar'):
                try:value=format(w.iface_range_value.CurrentValue,'.15g')
                except Exception:pass
                if info.handle and win32gui.GetClassName(info.handle).lower()=='msctls_trackbar32':
                    value=str(win32gui.SendMessage(info.handle,0x400,0,0))
            if info.control_type in ('List','Pane'):
                try:value=format(w.iface_scroll.CurrentVerticalScrollPercent,'.15g')
                except Exception:pass
                if info.handle and win32gui.GetClassName(info.handle).lower()=='listbox':
                    import win32con
                    value=str(win32gui.SendMessage(info.handle,win32con.LB_GETTOPINDEX,0,0))
            try:checked=bool(w.get_toggle_state())
            except Exception:pass
            text=info.name
            if info.control_type=="Text" and info.handle:
                try:text=win32gui.GetWindowText(info.handle)
                except Exception:pass
            controls.append(Control(id=ident,role=info.control_type,name=info.name[:300],automation_id=info.automation_id,
                enabled=w.is_enabled(),visible=w.is_visible(),password=password,value=value,checked=checked,
                attributes={"text":"" if password else text[:1000]}))
            handles[ident]=w
        self.seq+=1;self.handles=handles
        return observation(self.seq,f"hwnd:{self.contract.target.hwnd}",controls)
    def act(self,action,step,value):
        self.identity()
        if step.op in ("read","wait","copy"):return
        w=self.handles.get(action.control_id)
        if w is None:raise Stop("CONTROL_STALE")
        # UIA patterns do not move the pointer or wrestle keyboard focus.
        if step.op=="fill":w.set_edit_text(value)
        elif step.op=="click":w.invoke()
        elif step.op=="select":w.select(value)
        elif step.op in ("check","uncheck"):
            expected=step.op=="check"
            if bool(w.get_toggle_state())!=expected:w.toggle()
        elif step.op=='paste':
            from .clipboard import paste_with_restore
            paste_with_restore(value,w.set_edit_text)
        elif step.op=='scroll':
            try:w.iface_scroll.Scroll(2,4)
            except Exception:raise Stop('UIA_SCROLL_PATTERN_UNAVAILABLE') from None
        elif step.op=='range':
            try:
                pattern=w.iface_range_value;number=float(value)
                if not pattern.CurrentMinimum<=number<=pattern.CurrentMaximum or pattern.CurrentIsReadOnly:raise ValueError()
                import win32gui
                if w.handle and win32gui.GetClassName(w.handle).lower()=='msctls_trackbar32':
                    # Verified native trackbar template. No caller-supplied message IDs.
                    if number!=int(number):raise ValueError()
                    win32gui.SendMessage(w.handle,0x405,1,int(number))
                    win32gui.SendMessage(win32gui.GetParent(w.handle),0x114,4|(int(number)<<16),w.handle)
                else:pattern.SetValue(number)
            except Exception:raise Stop('UIA_RANGE_PATTERN_UNAVAILABLE') from None
        else:raise Stop("WINDOWS_PATTERN_UNSUPPORTED")
    def close(self):pass

def single_driver(contract):
    if contract.target.driver=="browser":raise Stop("LEGACY_BROWSER_RETIRED_USE_OFFICIAL_CHROME")
    if contract.target.driver=="windows":return Windows(contract)
    raise Stop("NO_RELIABLE_STRUCTURED_ADAPTER")

class Surfaces:
    def __init__(self,contract):self.contract=contract;self.drivers={};self.current='main'
    def open(self):self.activate('main')
    def activate(self,name):
        if name not in {'main',*self.contract.targets}:raise Stop('SURFACE_DENIED','blocked')
        if name not in self.drivers:
            target=self.contract.target if name=='main' else self.contract.targets[name]
            child=self.contract.model_copy(update={'target':target,'targets':{}})
            d=single_driver(child)
            d.input_guard=getattr(self,'input_guard',None)
            d.open();self.drivers[name]=d
        self.current=name
    @property
    def supported_ops(self):return self.drivers[self.current].supported_ops
    def observe(self):return self.drivers[self.current].observe().model_copy(update={'surface':self.current})
    def act(self,*args):return self.drivers[self.current].act(*args)
    def close(self):
        for d in self.drivers.values():d.close()

def create_driver(contract,input_guard=None,browser_session=None):
    if contract.target.connection=='official_chrome':
        if browser_session is None:raise Stop('CHROME_CODEX_SESSION_REQUIRED')
        if any(t.connection!='official_chrome' for t in contract.targets.values()):raise Stop('CHROME_MIXED_DESKTOP_REQUIRES_SEPARATE_TASK')
        from .chrome_session import ChromeSessionDriver
        return ChromeSessionDriver(contract,browser_session)
    if any(t.connection=='official_chrome' for t in contract.targets.values()):raise Stop('CHROME_NAMED_SURFACES_NOT_IMPLEMENTED')
    if any(t.driver=='browser' for t in [contract.target,*contract.targets.values()]):
        raise Stop('LEGACY_BROWSER_RETIRED_USE_OFFICIAL_CHROME')
    driver=Surfaces(contract) if contract.targets else single_driver(contract)
    driver.input_guard=input_guard
    return driver
