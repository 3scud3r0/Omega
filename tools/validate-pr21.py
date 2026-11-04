#!/usr/bin/env python3
"""Reproduce executable PR21 evidence without promoting the prepared compiler."""
from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
import argparse
import json
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from omega_sovereign.models import call
from omega_sovereign.hardware import tool
from omega_sovereign.native import build_crypto
from omega_sovereign.bft import experiment as bft
from omega_sovereign.network import experiment as network
from omega_sovereign.air_fri import prove,verify,canonical
from omega_self_evolve_v2.ouroboros import prepare
from omega_platform.sandbox import run,trusted
from omega_platform.budget import COMPILER_BUDGET,PROOF_BUDGET,BUILD_BUDGET
from omega_selfhost.proof import lake_binary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve()
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    paths=[]
    for directory in ('omega_selfhost','omega_sovereign','omega_net','omega_zk','omega_security','omega_self_evolve_v2','civilizacao_agentes','sovereign','testes/pr21'):
        paths += [p for p in (ROOT/directory).rglob('*') if p.suffix in ('.py','.omega','.S','.h') and not p.is_symlink()]
    paths += [ROOT/'formal'/f'{name}.lean' for name in ('Bisimulation','CompilerCorrectness','ConsensusSafety','CryptoTiming')]
    paths += [Path(__file__).resolve(),ROOT/'formal/tensor/lakefile.lean']
    report={'format':'omega-pr21-evidence-1','all_requirements_complete':False,
            'inputs':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}}
    source='funcao principal() { var i=0; var s=0; enquanto(i<50) { s=s+i; i=i+1; } retornar s; }'
    artifact=call('backend',{'source':source,'registers':[9,18]});again=call('backend',{'source':source,'registers':[9,18]})
    if artifact['elf_hex']!=again['elf_hex']:raise ValueError('Nonreproducible binary')
    binary=out/'loop.elf';binary.write_bytes(bytes.fromhex(artifact.pop('elf_hex')));binary.chmod(0o500)
    (out/'loop.omega').write_text(source);(out/'backend.json').write_text(json.dumps(artifact,indent=2)+'\n')
    executed=run([tool('qemu-riscv64'),binary],readonly=[binary],threads=True,budget=COMPILER_BUDGET)
    if not executed.ok or int(executed.stdout,16)!=1225:raise ValueError('Native loop result')
    report['native_backend']={'sha256':sha256(binary.read_bytes()).hexdigest(),'allocation':artifact['allocation'],
                              'relocations':artifact['relocations'],'execution':asdict(executed),'bootstrap_uses_c_gmp':True,'target_uses_c_gmp':False}
    report['crypto']=build_crypto(out/'crypto-fixed',fixed_field=True)
    point=out/'x25519.input';point.write_bytes(bytes.fromhex('77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a')+b'\x09'+bytes(31))
    result=run([tool('qemu-riscv64'),out/'crypto-fixed','x25519',point],readonly=[out/'crypto-fixed',point],threads=True,budget=COMPILER_BUDGET)
    if not result.ok or result.stdout.strip()!='8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a':raise ValueError('X25519 vector')
    report['crypto']['vector_execution']=asdict(result)
    report['network']=network(out/'network')
    if not report['network']['authenticated']:raise ValueError('Baremetal handshake failed')
    report['bft']=bft(out/'bft')
    native=call('stark',{'start':3,'c':5,'steps':32});proof=prove(3,5,32,trace=native['trace'])
    if not verify(proof,proof['statement']):raise ValueError('AIR/FRI proof rejected')
    (out/'air-proof.json').write_bytes(canonical(proof))
    report['air_fri']={'valid':True,'omega_fft':True,'steps':32,'bytes':len(canonical(proof)),'zero_knowledge':False}
    report['ouroboros']=prepare(out/'ouroboros')
    lean=trusted([lake_binary(),'build','Bisimulation','CompilerCorrectness','ConsensusSafety','CryptoTiming'],cwd=ROOT/'formal/tensor',budget=PROOF_BUDGET)
    (out/'lean.log').write_text(lean.stdout+lean.stderr)
    if not lean.ok or 'sorryAx' in lean.stdout or 'Lean.ofReduceBool' in lean.stdout:raise ValueError('Formal validation failed')
    report['lean']={'exit':lean.returncode,'seconds':lean.wall_seconds,'scope':'additive RV64 fragment, quorum lemmas, word select and fixed-work model'}
    tests=trusted([sys.executable,'-m','pytest','testes/pr21','-q',f'--junitxml={out}/tests.xml'],cwd=ROOT,budget=BUILD_BUDGET)
    (out/'tests.log').write_text(tests.stdout+tests.stderr)
    suites=list(ET.parse(out/'tests.xml').getroot().iter('testsuite')) if (out/'tests.xml').is_file() else []
    report['tests']={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','errors','failures','skipped')}
    report['validation_passed']=tests.ok
    report['artifact_sha256']={str(p.relative_to(out)):sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':str(out/'report.json'),'passed':tests.ok,'tests':report['tests']}))
    return 0 if tests.ok else 1


if __name__=='__main__':raise SystemExit(main())
