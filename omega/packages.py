"""Offline, root-confined package verification and deterministic resolution."""
import hashlib,os,stat
from pathlib import Path,PurePosixPath
from .package_lock import validate,canonical
def order(lock):
    validate(lock);done=set();active=[];result=[]
    def visit(name):
        if name in active:raise ValueError('Package cycle: '+' -> '.join([*active,name]))
        if name in done:return
        active.append(name)
        for child in sorted(lock['packages'][name]['dependencies']):visit(child)
        active.pop();done.add(name);result.append(name)
    for name in sorted(lock['packages']):visit(name)
    return tuple(result)
def verify(lock,root):
    root=Path(root).resolve(strict=True);result=[];total=0
    for name in order(lock):
        for relative,expected in sorted(lock['packages'][name]['files'].items()):
            from omega_security.filesystem import read
            data=read(root,name+'/'+relative,limit=64*1024**2-total)
            total+=len(data)
            if total>64*1024**2:raise ValueError('Package byte budget exceeded')
            digest=hashlib.sha256(data)
            if digest.hexdigest()!=expected:raise ValueError('Package integrity mismatch: '+name+'/'+relative)
        result.append(name)
    return tuple(result)
