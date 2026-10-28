"""Four native generations, full map proof, differential probe, then a bundle."""
import hashlib
import json
from pathlib import Path
import time
from .rules import validate_rule,install_template
from omega_selfhost.proof_protocol import encode


PROTECTED=('omega_selfhost/driver.py','omega_selfhost/proof.py','omega/certified_proof.py',
           'omega_self_mutate/activation.py','omega_self_mutate/rules.py','omega_self_mutate/bootstrap.py',
           'omega_agent_sandbox/runtime.py','formal/tensor/Main.lean')


def protected_hashes():
    root=Path(__file__).resolve().parents[1]
    return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in PROTECTED if (root/p).is_file()}


def rebootstrap(source,directory,seed=None):
    from omega_selfhost.driver import compiler,cc
    from omega_platform.sandbox import run
    from omega_platform.budget import COMPILER_BUDGET
    root=Path(directory).absolute();root.mkdir(parents=True,exist_ok=False)
    path=root/'compiler.omega';path.write_text(source)
    current=Path(seed or compiler());records=[]
    for stage in range(4):
        c=root/f'stage{stage}.c';binary=root/f'stage{stage}'
        start=time.perf_counter_ns()
        run([current,path,c],readonly=[path],writable=[root],budget=COMPILER_BUDGET,check=True)
        cc(c,binary)
        records.append({'stage':stage,'c_sha256':hashlib.sha256(c.read_bytes()).hexdigest(),
                        'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
                        'build_ns':time.perf_counter_ns()-start})
        current=binary
    final=root/'stage4.c'
    run([current,path,final],readonly=[path],writable=[root],budget=COMPILER_BUDGET,check=True)
    if len({r['c_sha256'] for r in records}|{hashlib.sha256(final.read_bytes()).hexdigest()})!=1 or records[2]['binary_sha256']!=records[3]['binary_sha256']:
        raise ValueError('Four-stage bootstrap did not stabilize')
    return {'stages':records,'binary':str(current),'source':str(path),'fixed_point':True}


def evolve(rule,directory,*,activate_default=False):
    from omega_selfhost.driver import PACKAGE,verify_optimization,cc,run as run_native
    from omega_platform.sandbox import run
    from omega_platform.budget import COMPILER_BUDGET
    rule=validate_rule(rule['lhs'],rule['rhs'])
    baseline=(PACKAGE/'compiler.omega').read_text();source=install_template(baseline,rule)
    root=Path(directory).absolute();root.mkdir(parents=True,exist_ok=False)
    protected=protected_hashes()
    boot=rebootstrap(source,root/'bootstrap')
    # Probe is derived from the rule statement, not from a handwritten result.
    from omega_refine_check.syntax import render
    declarations='\n'.join(f'parametro {name}={i+2};' for i,name in enumerate(rule['variables']))
    probe=root/'probe.omega';probe.write_text(declarations+'\ntensor y='+render(rule['lhs'])+';\nmostrar y;\n')
    candidate=root/'probe.c'
    run([boot['binary'],probe,candidate,'--optimize'],readonly=[probe],writable=[root],budget=COMPILER_BUDGET,check=True)
    witness=json.loads(Path(str(candidate)+'.opt.json').read_text())
    if not any(entry['regra']=='synth_'+rule['id'] for entry in witness['regras']):raise ValueError('New compiler did not exercise the proposed mutation')
    proof=verify_optimization(witness,proof_path=root/'optimization.lean')
    cc(candidate,root/'probe')
    result,admission=run_native(root/'probe')
    original_nodes=len(witness['original']['nos']);optimized_nodes=len(witness['otimizado']['nos'])
    if optimized_nodes>=original_nodes:raise ValueError('Mutation did not improve the declared IR-node objective')
    if protected_hashes()!=protected:raise ValueError('Mutation modified its verifier or action boundary')
    record={'format':'omega-self-mutation-1','rule':rule,'bootstrap':boot,'proof':proof,'native_admission':admission,
            'protected':protected,'objective':{'metric':'IR nodes on the generated probe','before':original_nodes,'after':optimized_nodes},
            'files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()},
            'compiler_relative':'bootstrap/stage3','default_activated':False}
    (root/'generation.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    if activate_default:
        from .activation import activate
        record['activation']=activate(root)
    return record
