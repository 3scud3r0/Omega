"""Content-addressed local storage with atomic publication and hash-on-read."""
import hashlib,os,re,tempfile,fcntl
from pathlib import Path
class ContentCache:
    def __init__(self,root,max_bytes=64*1024**2):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True);self.max_bytes=max_bytes
        if type(max_bytes) is not int or not 0<max_bytes<=1024**3:raise ValueError('Invalid cache quota')
    def _path(self,key):
        if type(key) is not str or not re.fullmatch('[0-9a-f]{64}',key):raise ValueError('Invalid content address')
        return self.root/key
    def put(self,data):
        fd=os.open(self.root/'.quota-lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'r+b') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            return self._put(data)
    def _put(self,data):
        if type(data) is not bytes or len(data)>self.max_bytes:raise ValueError('Content budget exceeded')
        key=hashlib.sha256(data).hexdigest();target=self._path(key)
        if target.exists():self.get(key);return key
        current=sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())
        if current+len(data)>self.max_bytes:raise ValueError('Cache quota exceeded')
        fd,name=tempfile.mkstemp(prefix='.content-',dir=self.root)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            try:os.link(name,target)
            except FileExistsError:self.get(key)
        finally:os.unlink(name)
        return key
    def get(self,key):
        path=self._path(key);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:data=stream.read(self.max_bytes+1)
        if len(data)>self.max_bytes or hashlib.sha256(data).hexdigest()!=key:raise ValueError('Corrupt cached content')
        return data
