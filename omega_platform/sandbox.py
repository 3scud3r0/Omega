"""Fail-closed Linux execution: namespaces, explicit mounts, seccomp and rlimits.

No candidate environment, home directory, network proxy or credential is inherited.
Trusted build/proof tools use resource limits but are a separate trust boundary.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
import errno
import os
from pathlib import Path
import platform
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
from typing import Mapping,Sequence

from .budget import Budget


class IsolationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Outcome:
    argv: tuple[str,...]
    returncode: int
    stdout: str
    stderr: str
    wall_seconds: float
    timed_out: bool
    sandboxed: bool
    budget: dict

    @property
    def ok(self):return self.returncode==0 and not self.timed_out
    @property
    def signal(self):return -self.returncode if self.returncode<0 else None


class ExecutionFailure(RuntimeError):
    def __init__(self,outcome: Outcome):
        self.outcome=outcome
        reason='wall-time budget exceeded' if outcome.timed_out else f'exit {outcome.returncode}'
        super().__init__(f'Execution {reason}: {outcome.argv[0]}\n{outcome.stderr[-6000:]}')


def _tool(name):
    pinned=Path(__file__).resolve().parents[2]/'.tools/bubblewrap-0.12.0/bin/bwrap'
    value=str(pinned) if name=='bwrap' and pinned.is_file() else shutil.which(name)
    if not value:raise IsolationUnavailable(f'Required execution tool unavailable: {name}')
    return value


def _seccomp(instrumented=False,threads=False,subprocesses=False):
    # Classic BPF over seccomp_data, x86-64 only. Unknown architectures fail closed.
    if platform.machine() not in ('x86_64','amd64'):
        raise IsolationUnavailable('The implemented seccomp policy currently supports x86-64')
    instructions=[(0x20,0,0,4),(0x15,1,0,0xC000003E),(0x06,0,0,0x80000000),
                  (0x20,0,0,0),(0x45,0,1,0x40000000),(0x06,0,0,0x80000000)]
    # Network and process escape/creation syscalls. The sandbox has one candidate
    # process; the supervisor is outside its PID namespace.
    denied=(41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,101,
            165,166,169,175,176,246,248,249,250,272,288,298,299,307,308,
            310,311,313,317,321,322,323,425,426,427,428,429,430,431,432,433,435,438,442)
    # LeakSanitizer inspects its own address space with a helper. Both the
    # helper and traced process stay inside the private PID namespace.
    if instrumented or subprocesses:
        allowed=(56,57,58,435,101) if instrumented else (56,57,58,435)
        denied=tuple(n for n in denied if n not in allowed)
        # Permit helpers inside this namespace, never new namespaces or a
        # changed parent. clone3 cannot be inspected through a user pointer.
        instructions.extend([(0x15,0,1,435),(0x06,0,0,0x00050000|errno.ENOSYS),
                             (0x15,0,5,56),(0x20,0,0,16),(0x54,0,0,0x7E028080),
                             (0x15,1,0,0),(0x06,0,0,0x00050000|errno.EPERM),
                             (0x06,0,0,0x7FFF0000)])
    if threads and not (instrumented or subprocesses):
        # glibc falls back from clone3 on ENOSYS. Permit only a clone sharing
        # VM, signal handlers and thread group; no independent child process.
        denied=tuple(n for n in denied if n not in (56,435))
        instructions.extend([(0x15,0,1,435),(0x06,0,0,0x00050000|errno.ENOSYS),
                             (0x15,0,5,56),(0x20,0,0,16),(0x54,0,0,0x10900),
                             (0x15,1,0,0x10900),(0x06,0,0,0x00050000|errno.EPERM),
                             (0x06,0,0,0x7FFF0000)])
    for number in denied:
        instructions.extend([(0x15,0,1,number),(0x06,0,0,0x00050000|errno.EPERM)])
    instructions.append((0x06,0,0,0x7FFF0000))
    return b''.join(struct.pack('HBBI',*insn) for insn in instructions)


def clean_environment(budget: Budget,extra: Mapping[str,str]|None=None):
    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
         'TMPDIR':'/tmp','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
         'OMEGA_FUEL':str(budget.fuel),'OMEGA_DEPTH':str(budget.depth)}
    allowed={'ASAN_OPTIONS','UBSAN_OPTIONS','LSAN_OPTIONS'}
    for name,value in (extra or {}).items():
        if name not in allowed or not isinstance(value,str):
            raise ValueError(f'Candidate environment variable is not permitted: {name}')
        env[name]=value
    return env


def _limits(budget: Budget,instrumented=False,namespace=False):
    return [_tool('prlimit'),f'--as={32*1024**4 if instrumented else budget.memory_bytes}',f'--cpu={budget.cpu_seconds}',
            f'--fsize={max(budget.output_bytes,budget.file_bytes)}',*([f'--nproc={budget.processes}'] if not namespace else []),
            f'--nofile={budget.open_files}',f'--stack={budget.stack_bytes}','--core=0','--']


def _capture(command,original,budget,*,cwd=None,env=None,pass_fds=(),sandboxed=False):
    with tempfile.TemporaryDirectory(prefix='omega-output-') as tmp:
        out=Path(tmp)/'stdout';err=Path(tmp)/'stderr';started=time.monotonic();expired=False
        with out.open('wb') as stdout,err.open('wb') as stderr:
            try:
                supervisor=[sys.executable,str(Path(__file__).with_name('_supervisor.py')),
                            ','.join(map(str,pass_fds)),*map(str,command)]
                child=subprocess.Popen(supervisor,cwd=cwd,env=env,stdout=stdout,stderr=stderr,
                                       stdin=subprocess.DEVNULL,pass_fds=pass_fds,
                                       start_new_session=True)
            except OSError as exc:
                raise IsolationUnavailable(f'Could not launch execution supervisor: {exc.strerror}') from exc
            try:
                # Poll output size as well as wall time. File limits also protect
                # disk use if a candidate emits faster than the poll interval.
                while child.poll() is None:
                    if time.monotonic()-started>budget.wall_seconds:
                        expired=True;break
                    if out.stat().st_size+err.stat().st_size>budget.output_bytes:
                        break
                    time.sleep(0.01)
                if child.poll() is None:
                    child.terminate()
                code=child.wait(timeout=5)
            finally:
                # Kill any surviving descendants of trusted tools too.
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        with out.open('rb') as stream:stdout=stream.read(budget.output_bytes).decode('utf-8','replace')
        with err.open('rb') as stream:stderr=stream.read(budget.output_bytes).decode('utf-8','replace')
        if out.stat().st_size+err.stat().st_size>budget.output_bytes:
            stderr+='\nOmega supervisor: output budget exceeded'
            if code==0:code=-signal.SIGXFSZ
        return Outcome(tuple(map(str,original)),code,stdout,stderr,time.monotonic()-started,
                       expired,sandboxed,asdict(budget))


def run(argv:Sequence[str|Path],*,budget=Budget(),readonly=(),writable=(),
        cwd='/work',extra_env=None,check=False,_instrumented=False,threads=False,_subprocesses=False):
    if not argv:raise ValueError('An executable is required')
    exe=Path(argv[0]).resolve(strict=True)
    if not exe.is_file():raise ValueError('Executable must be a file')
    bwrap=_tool('bwrap');prlimit=_tool('prlimit');policy=_seccomp(_instrumented,threads,_subprocesses)
    with tempfile.TemporaryFile() as filters:
        filters.write(policy);filters.flush();filters.seek(0)
        args=[bwrap,'--unshare-all','--die-with-parent','--new-session','--cap-drop','ALL',
              '--size',str(budget.file_bytes),'--tmpfs','/']
        for path in ('/usr/lib','/lib','/lib64'):
            if Path(path).exists():args+=['--ro-bind',path,path]
        args+=['--dir','/etc']
        if Path('/etc/ld.so.cache').is_file():args+=['--ro-bind','/etc/ld.so.cache','/etc/ld.so.cache']
        args+=['--proc','/proc','--dir','/dev','--dir','/tmp','--dir','/work']
        for path in ('/dev/null','/dev/zero','/dev/urandom','/dev/random'):
            args+=['--dev-bind',path,path]
        args+=['--symlink','/proc/self/fd','/dev/fd']
        ro=[exe,Path(prlimit).resolve(),*[Path(p).resolve(strict=True) for p in readonly]]
        rw=[Path(p).resolve(strict=True) for p in writable]
        for path in rw:
            if not path.is_dir():raise ValueError('Writable capabilities must name directories')
            if path in (Path('/'),Path('/usr'),Path('/etc'),Path('/workspace')):
                raise ValueError('Broad writable mounts are forbidden')
        for path in [*ro,*rw]:
            if any(path==r or r in path.parents for r in (Path('/proc'),Path('/dev'),Path('/sys'))):
                raise ValueError('Kernel/device mounts cannot be granted')
        # Explicit mounts retain their absolute paths; callers do not need to
        # rewrite generated proof or compiler output paths.
        for path in rw:args+=['--bind',str(path),str(path)]
        for path in ro:args+=['--ro-bind',str(path),str(path)]
        args+=['--chdir',str(cwd),'--seccomp',str(filters.fileno()),'--',str(Path(prlimit).resolve()),
               f'--nproc={budget.processes}','--',str(exe),*map(str,argv[1:])]
        result=_capture(_limits(budget,_instrumented,namespace=True)+args,argv,budget,env=clean_environment(budget,extra_env),
                        pass_fds=(filters.fileno(),),sandboxed=True)
    if result.returncode and ('bwrap:' in result.stderr or 'prlimit:' in result.stderr):
        raise IsolationUnavailable(result.stderr[-2000:])
    if check and not result.ok:raise ExecutionFailure(result)
    return result


def trusted(argv,*,budget,cwd=None,check=False):
    """Resource-limit a trusted tool; do not call this for candidate programs."""
    result=_capture(_limits(budget)+list(map(str,argv)),argv,budget,cwd=cwd,
                    env=os.environ.copy(),sandboxed=False)
    if check and not result.ok:raise ExecutionFailure(result)
    return result


def c_tool(argv,*,inputs,output_directory,budget,check=False):
    """Trusted C toolchain processing generated C inside a restricted filesystem.

    GCC may spawn cc1/as/ld, but cannot read the caller's workspace or secrets
    through preprocessor directives in generated C. Only its system toolchain,
    explicit inputs and output directory are granted.
    """
    for path in inputs:
        if Path(path).is_symlink():raise ValueError('Compiler inputs cannot be symlinks')
    system=[p for p in ('/usr/bin','/bin','/usr/include','/usr/libexec') if Path(p).exists()]
    return run(argv,readonly=[*system,*inputs],writable=[output_directory],
               budget=budget,check=check,_subprocesses=True)


def instrumented(argv,**kwargs):
    """Diagnostic ASan/LSan targets only; never a production execution profile.

    ASan requires a 20-TiB shadow reservation. A finite 32-TiB virtual limit
    replaces the normal address-space quota. ASan's RSS watchdog provides an
    additional diagnostic guard, not a hard physical-memory guarantee. File,
    CPU, wall, output and namespace restrictions remain active.
    """
    budget=kwargs.get('budget',Budget())
    return run(argv,_instrumented=True,extra_env={
        'ASAN_OPTIONS':f'detect_leaks=1:abort_on_error=1:hard_rss_limit_mb={budget.memory_bytes//1024**2}',
        'LSAN_OPTIONS':'exitcode=86','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'},**kwargs)
