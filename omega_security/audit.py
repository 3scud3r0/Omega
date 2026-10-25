"""Hash-chained audit with an external anchor. No filesystem immutability claim."""
import fcntl,hashlib,json,os
from pathlib import Path
from .secrets import redact
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
class AuditLog:
    def __init__(self,path,anchor=None,max_bytes=8*1024**2):self.path=Path(path);self.anchor=anchor;self.max_bytes=max_bytes
    def _decode(self,data):
        head='0'*64;records=[]
        for line in data.splitlines():
            item=json.loads(line);payload=item['payload']
            expected=hashlib.sha256(bytes.fromhex(head)+canonical(payload)).hexdigest()
            if item.get('previous')!=head or item.get('sha256')!=expected:raise ValueError('Audit chain broken')
            head=expected;records.append(item)
        if self.anchor is not None and head!=self.anchor:raise ValueError('Audit anchor mismatch')
        return records,head
    def append(self,event):
        fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'r+b') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX);data=stream.read(self.max_bytes+1)
            if len(data)>self.max_bytes:raise ValueError('Audit quota exceeded')
            _,head=self._decode(data);payload=redact(event)
            digest=hashlib.sha256(bytes.fromhex(head)+canonical(payload)).hexdigest()
            record={'previous':head,'sha256':digest,'payload':payload};encoded=canonical(record)+b'\n'
            if len(data)+len(encoded)>self.max_bytes:raise ValueError('Audit quota exceeded')
            stream.seek(0,2);stream.write(encoded);stream.flush();os.fsync(stream.fileno());self.anchor=digest
        return digest
    def read(self):
        fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as stream:data=stream.read(self.max_bytes+1)
        if len(data)>self.max_bytes:raise ValueError('Audit quota exceeded')
        return self._decode(data)[0]
