"""Root-anchored POSIX file operations; no directory-component symlink traversal."""
import hashlib,os,secrets,stat
from pathlib import Path,PurePosixPath
from contextlib import contextmanager
@contextmanager
def parent(root,relative,create=False):
    path=PurePosixPath(relative)
    if path.is_absolute() or str(path)!=relative or not path.parts or any(p in {'.','..','.git'} for p in path.parts) or '\\' in relative or ':' in relative:raise PermissionError('Unsafe relative file path')
    directory=os.open(Path(root).resolve(strict=True),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            if create:
                try:os.mkdir(part,0o700,dir_fd=directory)
                except FileExistsError:pass
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory);directory=child
        yield directory,path.parts[-1]
    finally:os.close(directory)
def read(root,relative,limit=16*1024**2):
    with parent(root,relative) as (directory,name):
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        with os.fdopen(fd,'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Regular file required')
            data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('File byte budget exceeded')
    return data
def write(root,relative,data,expected_sha256=None,create=False):
    if type(data) is not bytes or len(data)>16*1024**2:raise ValueError('Invalid file payload')
    with parent(root,relative,create=create) as (directory,name):
        if expected_sha256 is not None:
            fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
            with os.fdopen(fd,'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Regular source required')
                previous=stream.read(16*1024**2+1)
            if hashlib.sha256(previous).hexdigest()!=expected_sha256:raise ValueError('Source changed before write')
        temporary='.omega-write-'+secrets.token_hex(12)
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,name,src_dir_fd=directory,dst_dir_fd=directory);os.fsync(directory)
        finally:
            try:os.unlink(temporary,dir_fd=directory)
            except FileNotFoundError:pass
    return hashlib.sha256(data).hexdigest()
