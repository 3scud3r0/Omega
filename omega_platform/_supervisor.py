"""Private Linux child reaper. No candidate data is interpreted as Python."""
import ctypes
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(36,1,0,0,0):raise OSError(ctypes.get_errno(),'subreaper unavailable')
    descriptors=tuple(int(x) for x in sys.argv[1].split(',') if x)
    child=None
    stopped=False
    def stop(signum,frame):
        nonlocal stopped
        stopped=True
        if child is not None:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
    signal.signal(signal.SIGTERM,stop)
    child=subprocess.Popen(sys.argv[2:],pass_fds=descriptors,start_new_session=True)
    if stopped:stop(signal.SIGTERM,None)
    code=child.wait()
    # Bubblewrap's monitor can be reparented before its outer process exits.
    # Adopt it here, terminate any survivor, and reap it before returning.
    while True:
        try:pid,_=os.waitpid(-1,os.WNOHANG)
        except ChildProcessError:break
        if not pid:
            # CONFIG_CHECKPOINT_RESTORE (the proc children file) is optional.
            # PPid in proc stat is available on supported Linux kernels.
            for entry in Path('/proc').iterdir():
                if not entry.name.isdigit():continue
                try:
                    fields=(entry/'stat').read_text().rsplit(') ',1)[1].split()
                    if int(fields[1])==os.getpid():os.kill(int(entry.name),signal.SIGKILL)
                except (FileNotFoundError,ProcessLookupError,PermissionError):pass
            time.sleep(0.001)
    if code<0:
        signal.signal(-code,signal.SIG_DFL)
        os.kill(os.getpid(),-code)
    return code


if __name__=='__main__':raise SystemExit(main())
