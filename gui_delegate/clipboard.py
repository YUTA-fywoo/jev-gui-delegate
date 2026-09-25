"""Bounded Win32 clipboard transaction; preserves HGLOBAL formats, never logs content."""
import ctypes as c
from contextlib import contextmanager
from .security import Stop,SECRET

u=c.WinDLL('user32',use_last_error=True);k=c.WinDLL('kernel32',use_last_error=True)
u.GetClipboardData.argtypes=[c.c_uint];u.GetClipboardData.restype=c.c_void_p
u.SetClipboardData.argtypes=[c.c_uint,c.c_void_p];u.SetClipboardData.restype=c.c_void_p
k.GlobalSize.argtypes=[c.c_void_p];k.GlobalSize.restype=c.c_size_t
k.GlobalLock.argtypes=[c.c_void_p];k.GlobalLock.restype=c.c_void_p
k.GlobalUnlock.argtypes=[c.c_void_p]
k.GlobalAlloc.argtypes=[c.c_uint,c.c_size_t];k.GlobalAlloc.restype=c.c_void_p
k.GlobalFree.argtypes=[c.c_void_p]

@contextmanager
def opened():
    import time
    for _ in range(5):
        if u.OpenClipboard(None):break
        time.sleep(.04)
    else:raise Stop('CLIPBOARD_BUSY')
    try:yield
    finally:u.CloseClipboard()

def snapshot_open():
    values=[];fmt=0;total=0
    while True:
        fmt=u.EnumClipboardFormats(fmt)
        if not fmt:break
        if fmt in (2,3,9,14,0x80,0x81,0x82,0x83,0x8e):raise Stop('CLIPBOARD_HANDLE_FORMAT_UNSUPPORTED')
        h=u.GetClipboardData(fmt);size=k.GlobalSize(h) if h else 0
        total+=size
        if not h or not size or total>16*1024*1024:raise Stop('CLIPBOARD_SNAPSHOT_UNAVAILABLE')
        ptr=k.GlobalLock(h)
        if not ptr:raise Stop('CLIPBOARD_SNAPSHOT_UNAVAILABLE')
        try:values.append((fmt,c.string_at(ptr,size)))
        finally:k.GlobalUnlock(h)
    return values

def put_open(values):
    allocated=[]
    try:
        for fmt,data in values:
            h=k.GlobalAlloc(2,len(data));ptr=k.GlobalLock(h)
            if not ptr:raise Stop('CLIPBOARD_ALLOCATION_FAILED','blocked')
            c.memmove(ptr,data,len(data));k.GlobalUnlock(h);allocated.append([fmt,h])
        if not u.EmptyClipboard():raise Stop('CLIPBOARD_WRITE_FAILED')
        for entry in allocated:
            if not u.SetClipboardData(*entry):raise Stop('CLIPBOARD_WRITE_FAILED')
            entry[1]=None
    finally:
        for _,h in allocated:
            if h:k.GlobalFree(h)

def paste_with_restore(text,apply):
    if SECRET.search(text) or len(text)>32000:raise Stop('SENSITIVE_INPUT_REQUIRES_USER')
    with opened():
        original=snapshot_open()
        # Persist only a current-user encrypted recovery envelope before any mutation.
        from . import storage
        import base64
        recovery=storage.DATA/'clipboard-recovery.dpapi'
        if recovery.exists():raise Stop('CLIPBOARD_RECOVERY_PENDING','blocked')
        storage.protect_directory(storage.DATA)
        storage.save(recovery,{'original':[(fmt,base64.b64encode(raw).decode()) for fmt,raw in original],'phase':'prepared'})
        try:put_open([(13,(text+'\0').encode('utf-16-le'))])
        except BaseException:
            # Still own the clipboard: restore on partial publication failure.
            put_open(original);recovery.unlink(missing_ok=True)
            raise
    # Windows can finish synthesizing clipboard formats when CloseClipboard runs.
    ours=u.GetClipboardSequenceNumber()
    storage.save(recovery,{'original':[(fmt,base64.b64encode(raw).decode()) for fmt,raw in original],'phase':'published','sequence':ours})
    changed=False
    try:
        with opened():
            if u.GetClipboardSequenceNumber()!=ours:raise Stop('USER_CLIPBOARD_CHANGED','paused')
            h=u.GetClipboardData(13);ptr=k.GlobalLock(h)
            if not ptr:raise Stop('CLIPBOARD_READ_FAILED')
            try:value=c.wstring_at(ptr)
            finally:k.GlobalUnlock(h)
        if value!=text:raise Stop('CLIPBOARD_VALUE_MISMATCH','blocked')
    finally:
        with opened():
            changed=u.GetClipboardSequenceNumber()!=ours
            if not changed:put_open(original)
        if not changed:recovery.unlink(missing_ok=True)
        if changed:raise Stop('USER_CLIPBOARD_CHANGED','paused')
    # Restore before entering a driver call that could block. The observed clipboard
    # value is then applied through the control's semantic value interface.
    apply(value)

def restore_pending():
    from . import storage
    import base64
    path=storage.DATA/'clipboard-recovery.dpapi'
    if not path.exists():return {'restored':False,'pending':False}
    data=storage.read(path)
    with opened():
        if data.get('phase')!='published' or data.get('sequence')!=u.GetClipboardSequenceNumber():
            raise Stop('RECOVERY_NOT_APPLIED_NEW_CLIPBOARD','paused')
        put_open([(fmt,base64.b64decode(raw)) for fmt,raw in data['original']])
    path.unlink();return {'restored':True,'pending':False}
