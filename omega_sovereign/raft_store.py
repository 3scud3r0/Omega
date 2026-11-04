"""Host durability adapter for the Omega Raft core; no network or self-promotion.

A single process owns each directory. Replies are returned only after fsync of
the new hard state and the containing directory. Crash restart always drops
volatile leadership. This is not a bare-metal filesystem implementation.
"""
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import tempfile
from omega_security.encoding import canonical,decode
from .models import call


class Node:
    def __init__(self,directory,members,identity):
        self.path=Path(directory).resolve()
        self.path.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.path.stat().st_mode & 0o077:raise PermissionError('Private Raft store required')
        self.members=members;self.identity=identity;self.volatile=None;self.closed=False
        self.lock=os.open(self.path/'.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:os.close(self.lock);raise

    def _load(self):
        path=self.path/'state.json'
        try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        except FileNotFoundError:return None
        with os.fdopen(fd,'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Raft state must be a file')
            content=stream.read(256*1024+1)
        document=decode(content,max_bytes=256*1024,max_nodes=10000,max_depth=16)
        if set(document)!={'state','sha3_256','members','self'}:raise ValueError('Raft store schema')
        if document['members']!=self.members or document['self']!=self.identity:raise ValueError('Raft identity mismatch')
        if hashlib.sha3_256(canonical(document['state'])).hexdigest()!=document['sha3_256']:raise ValueError('Raft state integrity')
        return document['state']

    def step(self,events):
        if self.closed:raise ValueError('Raft node closed')
        request={'members':self.members,'self':self.identity,'events':events}
        hard=self._load()
        if hard is not None:request['hard_state']=hard
        if self.volatile is not None:request['volatile_state']=self.volatile
        result=call('raft',request);new=result['hard_state']
        if hard is not None:
            if new['term']<hard['term'] or new['commit']<hard['commit'] or new['log'][:hard['commit']]!=hard['log'][:hard['commit']]:
                raise ValueError('Raft durable invariant violation')
            if new['term']==hard['term'] and hard['vote']!=-1 and new['vote']!=hard['vote']:
                raise ValueError('Raft double vote')
        record={'state':new,'sha3_256':hashlib.sha3_256(canonical(new)).hexdigest(),
                'members':self.members,'self':self.identity}
        fd,name=tempfile.mkstemp(prefix='.state-',dir=self.path)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(canonical(record,max_bytes=256*1024,max_nodes=10000,max_depth=16));stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.path/'state.json')
            directory=os.open(self.path,os.O_DIRECTORY|os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        except BaseException:
            # Once durable outcome is uncertain, no more replies/operations are
            # allowed from this in-memory role. Recovery reloads the disk state.
            self.close();raise
        finally:
            if os.path.exists(name):os.unlink(name)
        self.volatile=result['volatile_state']
        return result

    def close(self):
        if not self.closed:os.close(self.lock);self.closed=True
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
