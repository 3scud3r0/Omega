"""Atomic version-pointer changes. Stable artifacts must already be authenticated."""
import json,os,tempfile,fcntl
from threading import RLock
from contextlib import contextmanager
from pathlib import Path
class Versions:
    def __init__(self,root):self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True);self.pointer=self.root/'current.json';self.lock=RLock()
    def current(self):
        if not self.pointer.exists():return None
        value=json.loads(self.pointer.read_text())
        if not isinstance(value.get('version'),str):raise ValueError('Invalid version pointer')
        return value
    def _write(self,value):
        fd,name=tempfile.mkstemp(prefix='.version-',dir=self.root)
        try:
            with os.fdopen(fd,'w') as stream:json.dump(value,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.pointer)
            directory=os.open(self.root,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        finally:Path(name).unlink(missing_ok=True)
    @contextmanager
    def transaction(self):
        with self.lock:
            fd=os.open(self.root/'.version-lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'r+b') as stream:
                fcntl.flock(stream,fcntl.LOCK_EX)
                yield
    def activate(self,version,decision,healthcheck):
        with self.transaction():return self._activate(version,decision,healthcheck)
    def _activate(self,version,decision,healthcheck):
        if decision.approved is not True or decision.subject!=version:raise PermissionError('Authenticated promotion decision required')
        previous=self.current();self._write({'version':version,'previous':previous['version'] if previous else None})
        try:
            if healthcheck(version) is not True:raise ValueError('Version failed health gate')
        except Exception:
            if previous is not None:self._write(previous)
            else:self.pointer.unlink(missing_ok=True)
            raise
        return self.current()
    def rollback(self):
        with self.transaction():return self._rollback()
    def _rollback(self):
        current=self.current()
        if not current or not current['previous']:raise ValueError('No previous stable version')
        self._write({'version':current['previous'],'previous':None});return self.current()
