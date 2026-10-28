import json
import subprocess
import sys
from pathlib import Path
from omega_cognition.pipeline import distill


def test_intent_to_proved_native_program_and_cli(tmp_path):
    spec={'variables':{'x':'true'},'ensures':'result == x+1',
          'examples':[{'inputs':{'x':'0'},'output':'1'},{'inputs':{'x':'3'},'output':'4'}]}
    result=distill('Increment a rational sensor',spec,tmp_path/'distilled',iterations=256)
    assert result['result']['verified'] and result['result']['native_admission']
    path=tmp_path/'qpu.json';path.write_text(json.dumps({'op':'+','a':'1/3','b':'2/3'}))
    process=subprocess.run([sys.executable,'-m','omega','cognition','qpu',str(path)],capture_output=True,text=True,check=True)
    assert json.loads(process.stdout)['value']=='1'


def test_new_commands_expose_help():
    for command in ('refine','synth','mutate','action','cognition'):
        process=subprocess.run([sys.executable,'-m','omega',command,'--help'],capture_output=True,text=True,check=True)
        assert 'usage:' in process.stdout


def test_profiler_measures_native_execution_separately_from_proof(tmp_path):
    from omega_self_mutate.profiler import profile_native
    source=tmp_path/'profile.omega';source.write_text('parametro x=2; tensor y=(x*2)-x; mostrar y;')
    result=profile_native(source,iterations=2)
    assert result['nodes']>1 and len(result['native_seconds'])==2
    assert result['native_admission'] and result['native_min_seconds']>0


def test_module_qualified_names_and_cpp_comments_remain_compatible(tmp_path):
    from omega.modules import link
    from omega_selfhost.driver import build_module,run
    library=tmp_path/'math.omega';library.write_text('// rational library\nexportar inc;funcao inc(x){retornar x+1;}')
    entry=tmp_path/'main.omega';entry.write_text('importar "math.omega" como m; // qualified symbol\nfuncao principal(){print(m::inc(2));retornar 0;}')
    binary=tmp_path/'program';build_module(entry,binary,root=tmp_path)
    from omega_platform.sandbox import run as execute
    assert execute([binary],check=True).stdout.strip()=='3'
