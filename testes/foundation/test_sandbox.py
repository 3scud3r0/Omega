from dataclasses import replace
import json
import os
from pathlib import Path
import shutil

import pytest

from omega_platform.budget import Budget
from omega_platform.sandbox import run,IsolationUnavailable
from omega_platform import sandbox

PYTHON=Path('/usr/bin/python3').resolve()


def execute(text,**kwargs):
    return run([PYTHON,'-c',text],**kwargs)


@pytest.mark.parametrize('threads',[False,True])
def test_no_network_secrets_host_files_or_external_writes(tmp_path,monkeypatch,threads):
    secret=tmp_path/'host-secret';secret.write_text('canary')
    monkeypatch.setenv('OMEGA_SECRET_CANARY','must-not-inherit')
    script=f'''
import os,socket
assert 'OMEGA_SECRET_CANARY' not in os.environ
assert 'GH_TOKEN' not in os.environ
assert not os.path.exists({str(secret)!r})
try:socket.socket()
except PermissionError:pass
else:raise AssertionError('socket allowed')
try:open({str(tmp_path/'outside')!r},'w')
except OSError:pass
else:raise AssertionError('external write allowed')
try:os.fork()
except PermissionError:pass
else:raise AssertionError('fork allowed')
print('restricted')
'''
    out=execute(script,check=True,threads=threads)
    assert out.stdout=='restricted\n' and out.sandboxed
    assert not (tmp_path/'outside').exists()


def test_explicit_write_capability_preserves_readonly_child(tmp_path):
    protected=tmp_path/'protected';protected.write_text('original')
    out=execute(f'''
open({str(tmp_path/'allowed')!r},'w').write('ok')
try:open({str(protected)!r},'w').write('bad')
except OSError:pass
else:raise AssertionError('readonly file overwritten')
''',writable=[tmp_path],readonly=[protected],check=True)
    assert out.ok and protected.read_text()=='original'
    assert (tmp_path/'allowed').read_text()=='ok'


def test_wall_cpu_address_space_and_output_quotas():
    out=execute('while True:pass',budget=Budget(wall_seconds=.15))
    assert out.timed_out and not out.ok and out.wall_seconds<3
    out=execute('while True:pass',budget=Budget(cpu_seconds=1,wall_seconds=4))
    assert not out.ok and not out.timed_out
    out=execute('x=bytearray(1024**3)',budget=Budget(memory_bytes=64*1024**2))
    assert not out.ok and 'MemoryError' in out.stderr
    out=execute('import os\nwhile True:os.write(1,b"x"*1024)',budget=Budget(output_bytes=1024,wall_seconds=3))
    assert not out.ok and len(out.stdout)<=1024


def test_private_scratch_has_aggregate_mount_quota():
    out=execute('open("/tmp/data","wb").write(b"x"*(8*1024**2))',
                budget=Budget(file_bytes=1024**2))
    assert not out.ok and 'No space left' in out.stderr


def test_isolation_unavailable_does_not_fall_back_to_host(monkeypatch):
    original=sandbox._tool
    def unavailable(name):
        if name=='bwrap':raise IsolationUnavailable('bwrap unavailable')
        return original(name)
    monkeypatch.setattr(sandbox,'_tool',unavailable)
    with pytest.raises(IsolationUnavailable,match='bwrap'):execute('print("unsafe")')


def test_no_orphaned_sandbox_monitor():
    def zombies():
        values=set()
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():continue
            try:
                fields=(entry/'stat').read_text().rsplit(') ',1)[1].split()
                if fields[0]=='Z' and (entry/'comm').read_text().strip()=='bwrap':values.add(entry.name)
            except (FileNotFoundError,ProcessLookupError,PermissionError):pass
        return values
    before=zombies()
    for _ in range(8):assert execute('pass').ok
    assert zombies()<=before


@pytest.mark.parametrize('field,value',[('wall_seconds',float('inf')),('memory_bytes',0),
                                      ('fuel',0),('depth',513),('cpu_seconds',True)])
def test_invalid_budget_rejected(field,value):
    with pytest.raises(ValueError):replace(Budget(),**{field:value})


def test_thread_capability_is_explicit():
    script='''import threading
t=threading.Thread(target=lambda:None)
t.start()
t.join()'''
    assert execute(script,threads=True).ok
    assert not execute(script).ok


def test_c_preprocessor_cannot_read_outside_build_capability(tmp_path):
    from omega_platform.budget import BUILD_BUDGET
    from omega_platform.sandbox import c_tool
    outside=tmp_path/'host';outside.mkdir()
    secret=outside/'secret.h';secret.write_text('#error PRIVATE_CANARY_MUST_NOT_LEAK\n')
    build=tmp_path/'build';build.mkdir()
    source=build/'input.c';source.write_text(f'#include "{secret}"\nint main(void){{return 0;}}\n')
    out=c_tool(['/usr/bin/cc',source,'-o',build/'program'],inputs=[source],
               output_directory=build,budget=BUILD_BUDGET)
    assert not out.ok and 'No such file' in out.stderr
    assert 'PRIVATE_CANARY_MUST_NOT_LEAK' not in out.stderr
