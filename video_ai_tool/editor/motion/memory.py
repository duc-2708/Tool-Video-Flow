"""Approximate Windows process-tree working set, sampled without dependencies."""
import os
import threading


def tree_working_set():
    if os.name!="nt": return None
    import ctypes as c
    from ctypes import wintypes as w
    class Entry(c.Structure):
        _fields_=[("size",w.DWORD),("usage",w.DWORD),("pid",w.DWORD),("heap",c.c_size_t),
            ("module",w.DWORD),("threads",w.DWORD),("parent",w.DWORD),("priority",w.LONG),
            ("flags",w.DWORD),("exe",w.WCHAR*260)]
    class Memory(c.Structure):
        _fields_=[("cb",w.DWORD),("faults",w.DWORD)]+[(n,c.c_size_t) for n in
            ("peak","working","paged_peak","paged","nonpaged_peak","nonpaged","pagefile","pagefile_peak")]
    kernel=c.WinDLL("kernel32",use_last_error=True);psapi=c.WinDLL("psapi",use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype=w.HANDLE;kernel.OpenProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    kernel.Process32FirstW.argtypes=[w.HANDLE,c.POINTER(Entry)];kernel.Process32NextW.argtypes=[w.HANDLE,c.POINTER(Entry)]
    psapi.GetProcessMemoryInfo.argtypes=[w.HANDLE,c.POINTER(Memory),w.DWORD]
    snap=kernel.CreateToolhelp32Snapshot(2,0)
    if snap==c.c_void_p(-1).value: return None
    entry=Entry();entry.size=c.sizeof(entry);parents={}
    try:
        ok=kernel.Process32FirstW(snap,c.byref(entry))
        while ok:
            parents[entry.pid]=entry.parent;ok=kernel.Process32NextW(snap,c.byref(entry))
    finally: kernel.CloseHandle(snap)
    family={os.getpid()}
    while True:
        expanded=family|{pid for pid,parent in parents.items() if parent in family}
        if expanded==family: break
        family=expanded
    total=0
    for pid in family:
        handle=kernel.OpenProcess(0x410,False,pid)
        if not handle: continue
        try:
            mem=Memory();mem.cb=c.sizeof(mem)
            if psapi.GetProcessMemoryInfo(handle,c.byref(mem),mem.cb): total+=mem.working
        finally: kernel.CloseHandle(handle)
    return total


class MemorySampler:
    def __enter__(self):
        self.peak=0;self.stop=threading.Event()
        def sample():
            while not self.stop.is_set():
                self.peak=max(self.peak,tree_working_set() or 0);self.stop.wait(.25)
        self.thread=threading.Thread(target=sample,daemon=True);self.thread.start();return self
    def __exit__(self,*args):
        self.stop.set();self.thread.join(timeout=2)
    @property
    def peak_mb(self): return round(self.peak/1024**2,1) if self.peak else None
