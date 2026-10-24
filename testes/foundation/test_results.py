from dataclasses import replace
import json
from pathlib import Path
import signal

import pytest

from omega_platform.results import Ok,Err,Code,Problem,PipelineFailure,attempt
from omega_platform.sandbox import run,ExecutionFailure,IsolationUnavailable,Outcome
from omega_platform.budget import Budget
from omega_selfhost import driver

PYTHON=Path('/usr/bin/python3').resolve()


def test_results_distinguish_none_success_failure_and_require_explicit_inspection():
    result=attempt('test',lambda:None)
    assert isinstance(result,Ok) and result.is_ok and result.unwrap() is None
    failure=attempt('test',lambda:(_ for _ in ()).throw(ValueError('invalid')))
    assert isinstance(failure,Err) and not failure.is_ok
    with pytest.raises(PipelineFailure) as raised:failure.unwrap()
    assert raised.value.__cause__ is failure.cause
    for result in (result,failure):
        with pytest.raises(TypeError):bool(result)
    with pytest.raises(ValueError):Err(None)
    with pytest.raises(TypeError):failure.problem.details['extra']='mutable'


def test_interruptions_propagate_and_unexpected_errors_retain_their_causes():
    for exc in (KeyboardInterrupt(),SystemExit(4)):
        def operation():raise exc
        with pytest.raises(type(exc)):attempt('test',operation)
    def bug():raise AssertionError('unexpected canary')
    error=attempt('test',bug)
    assert error.problem.code==Code.INTERNAL and isinstance(error.cause,AssertionError)
    assert 'canary' not in json.dumps(error.to_dict())


@pytest.mark.parametrize('script,budget,code',[
    ('while True:pass',Budget(wall_seconds=.15),Code.WALL),
    ('import os\nwhile True:os.write(1,b"x"*1024)',Budget(output_bytes=1024),Code.OUTPUT),
    # Bubblewrap normalizes this to 143; it cannot be distinguished from exit(143).
    ('import os,signal;os.kill(os.getpid(),signal.SIGTERM)',Budget(),Code.EXIT),
    ('raise SystemExit(9)',Budget(),Code.EXIT),
])
def test_real_supervisor_status_drives_structured_errors(script,budget,code):
    result=attempt('execute',run,[PYTHON,'-c',script],budget=budget,check=True)
    assert isinstance(result,Err) and result.problem.code==code
    assert result.problem.stage=='execute' and result.problem.details['returncode']!=0
    assert 'stderr' not in result.to_dict()['error']['details']


def test_stderr_cannot_impersonate_launcher_failure_or_resource_reason():
    script='import sys;print("bwrap: prlimit: timeout MemoryError SECRET_CANARY",file=sys.stderr);sys.exit(1)'
    result=attempt('execute',run,[PYTHON,'-c',script],check=True)
    assert result.problem.code==Code.EXIT
    assert 'SECRET_CANARY' not in json.dumps(result.to_dict())
    assert result.problem.details['termination']=='exit'


def test_launcher_status_and_seccomp_descriptors_not_visible_inside_namespace():
    script='''import os
for pid in os.listdir('/proc'):
 if not pid.isdigit():continue
 try:fds=os.listdir('/proc/'+pid+'/fd')
 except PermissionError:continue
 for fd in fds:
  try:target=os.readlink('/proc/'+pid+'/fd/'+fd)
  except FileNotFoundError:continue
  if int(fd)>2:assert target.startswith('anon_inode:'),(pid,fd,target)
print('status-is-private')'''
    assert run([PYTHON,'-c',script],check=True).stdout=='status-is-private\n'


def test_missing_isolation_and_ambiguous_kill_are_not_invented_memory_failures(monkeypatch):
    def unavailable():raise IsolationUnavailable('secret internal setup detail')
    result=attempt('execute',unavailable)
    assert result.problem.code==Code.ISOLATION and 'secret' not in result.problem.message
    status=Outcome(('candidate',),-signal.SIGKILL,'','MemoryError',.01,False,True,{})
    def killed():raise ExecutionFailure(status)
    assert attempt('execute',killed).problem.code==Code.SIGNAL


def test_normalized_signal_and_explicit_exit_are_not_falsely_distinguished():
    terminated=run([PYTHON,'-c','import os,signal;os.kill(os.getpid(),signal.SIGTERM)'])
    exited=run([PYTHON,'-c','raise SystemExit(143)'])
    assert terminated.returncode==exited.returncode==143
    assert terminated.termination==exited.termination=='exit'
    assert terminated.signal is exited.signal is None


def test_missing_launcher_status_never_accepts_a_success_code(monkeypatch):
    from omega_platform import sandbox
    monkeypatch.setattr(sandbox,'_capture',lambda *args,**kwargs:Outcome(('launcher',),0,'','',.01,False,True,{}))
    result=attempt('execute',run,[PYTHON,'-c','pass'],check=True)
    assert result.problem.code==Code.ISOLATION


def test_build_type_failure_is_explicit_before_codegen(tmp_path,monkeypatch):
    path=tmp_path/'bad.omega';path.write_text('perda l=[1,2];')
    def forbidden(*args,**kwargs):raise AssertionError('invalid code reached build')
    monkeypatch.setattr(driver,'build',forbidden)
    result=driver.build_checked(path,tmp_path/'binary')
    assert result.problem.code==Code.TYPE and result.problem.stage=='types'


def test_checked_run_and_cli_report_proof_failure_after_successful_execution(tmp_path,capsys):
    from omega.cli import principal
    source=tmp_path/'unverified.omega';source.write_text('funcao principal(){print("{\\"format\\":\\"wrong\\"}");retornar 0;}')
    binary=tmp_path/'unverified';assert driver.build_checked(source,binary).is_ok
    result=driver.run_checked(binary)
    assert result.problem.code==Code.PROOF and result.problem.stage=='proof'
    assert principal(['native-run',str(binary)])==1
    error=json.loads(capsys.readouterr().err)
    assert error['format']=='omega-result-1' and error['ok'] is False and error['error']['code']=='proof.failed'


def test_runtime_invalid_len_and_failed_print_are_not_success_sentinels(tmp_path):
    source=tmp_path/'contracts.c';binary=tmp_path/'contracts'
    source.write_text('#include "runtime.h"\n#include <unistd.h>\nint main(int argc,char **argv){ if(argc>1){close(1);o_print(o_str("x"));}else{o_len(o_num("3"));}return 0;}')
    driver.cc(source,binary)
    for args,message in (([],'Sequence or object required'),(['print'],'Print failed')):
        result=run([binary,*args])
        assert not result.ok and message in result.stderr
