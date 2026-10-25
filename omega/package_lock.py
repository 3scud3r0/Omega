"""Canonical local package locks; hashes are integrity checks, not authorization."""
import hashlib,json,re
from pathlib import PurePosixPath
from .typed_ir import _pairs
FORMAT='omega-package-lock-1'
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def validate(lock):
    if type(lock) is not dict or set(lock)!={'format','packages'} or lock['format']!=FORMAT:raise ValueError('Unknown package lock')
    if type(lock['packages']) is not dict or len(lock['packages'])>64:raise ValueError('Package budget exceeded')
    for name,item in lock['packages'].items():
        if not name.isidentifier() or type(item) is not dict or set(item)!={'version','files','dependencies'}:raise ValueError('Invalid package entry')
        if not re.fullmatch(r'\d+\.\d+\.\d+',item['version']):raise ValueError('Explicit semantic version required')
        if type(item['files']) is not dict or len(item['files'])>2048:raise ValueError('File budget exceeded')
        for path,digest in item['files'].items():
            p=PurePosixPath(path)
            if p.is_absolute() or str(p)!=path or '..' in p.parts or '\\' in path or ':' in path:raise ValueError('Unsafe package path')
            if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Invalid content digest')
        if type(item['dependencies']) is not list or len(set(item['dependencies']))!=len(item['dependencies']):raise ValueError('Invalid dependencies')
        if any(dep not in lock['packages'] for dep in item['dependencies']):raise ValueError('Missing locked dependency')
    return lock
def load(path):
    with open(path,'rb') as stream:data=stream.read(1024*1024+1)
    if len(data)>1024*1024:raise ValueError('Lock byte budget exceeded')
    value=json.loads(data,object_pairs_hook=_pairs);validate(value)
    if data!=canonical(value):raise ValueError('Noncanonical lock')
    return value
