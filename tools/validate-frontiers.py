#!/usr/bin/env python3
"""Collect actual execution/formal/FPGA evidence; never infer physical completion."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from omega_zk.execution import Engine
from omega_selfhost.proof import lake_binary
from omega_platform.sandbox import trusted
from omega_platform.budget import PROOF_BUDGET


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verifier',type=Path,required=True)
    parser.add_argument('--prover',type=Path)
    parser.add_argument('--fpga',type=Path)
    parser.add_argument('--tests',type=Path)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    inputs=[]
    for name in ('omega_zk','omega_selfhost','omega_sovereign','hardware/boot','hardware/tinytapeout','testes/zkvm'):
        inputs.extend(p for p in (ROOT/name).rglob('*') if 'target' not in p.parts and '__pycache__' not in p.parts and p.suffix in ('.rs','.toml','.lock','.py','.omega','.v','.sv','.S','.lpf','.json','.md'))
    inputs.extend(ROOT/'formal'/n for n in ('CompilerCorrectness.lean','Bisimulation.lean','ExpressionCompiler.lean','RiscvEncoding.lean'))
    inputs.extend(ROOT/n for n in ('requirements/sovereign-tools.json','requirements/cpu-py312.lock','pyproject.toml','scripts/setup-zkvm.sh','scripts/test.sh','tools/validate-frontiers.py'))
    record={'format':'omega-frontiers-evidence-v1','source_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'inputs':{str(p.relative_to(ROOT)):digest(p) for p in sorted(set(inputs)) if p.is_file()},
            'all_requested_requirements_complete':False}
    lean=trusted([lake_binary(),'build','Bisimulation','CompilerCorrectness','ExpressionCompiler','RiscvEncoding'],cwd=ROOT/'formal/tensor',budget=PROOF_BUDGET)
    log=lean.stdout+lean.stderr;(out/'lean.log').write_text(log)
    if not lean.ok or 'sorryAx' in log or 'Lean.ofReduceBool' in log:raise ValueError('Lean validation failed')
    record['formal']={'passed':True,'full_language_compiler_proved':False,
        'scope':['arithmetic AST to stack IR','positive ADDI fragment','ADDI byte encoding/decoding'],
        'log_sha256':digest(out/'lean.log')}
    engine=Engine(args.verifier)
    source=(ROOT/'omega_zk/examples/soma_privada.omega').read_text()
    program=engine.compile(source,10);image_id=engine.image_id(program)
    (out/'guest.elf').write_bytes(program.elf);(out/'journal.json').write_bytes(program.journal)
    (out/'image-id.txt').write_text(image_id+'\n')
    record['zkvm']={'image_id':image_id,'guest_sha256':digest(out/'guest.elf'),
        'verifier_sha256':digest(args.verifier),'target':'checked-u32 RV32IM with RISC Zero compatibility kernel',
        'real_proof_generated':False,'measured_proof_bytes':None,'measured_verify_us':None}
    if args.prover:
        proof,metrics=Engine(args.prover).prove(program,[3,7,0,0,0,0,0,0])
        checked=engine.verify(proof,image_id,program.journal)
        (out/'receipt.bin').write_bytes(proof)
        record['zkvm'].update(real_proof_generated=True,proving=metrics,verification=checked,
            measured_proof_bytes=len(proof),measured_verify_us=checked['verify_us'],proof_sha256=digest(out/'receipt.bin'))
    else:
        record['zkvm']['pending']='Real CPU prover build blocked by recursion-artifact network prerequisite; no substitute proof accepted'
    if args.fpga:
        fpga=args.fpga.resolve();manifest=json.loads((fpga/'manifest.json').read_text())
        for name,expected in manifest['artifacts'].items():
            if digest(fpga/name)!=expected:raise ValueError('FPGA artifact integrity: '+name)
        for name,expected in manifest['inputs'].items():
            if digest(fpga/name)!=expected:raise ValueError('FPGA input integrity: '+name)
            if name!='monitor.hex' and digest(ROOT/'hardware/boot'/name)!=expected:raise ValueError('FPGA source stale: '+name)
        if not manifest.get('mapped_simulation',{}).get('passed'):raise ValueError('Technology-mapped serial simulation required')
        record['fpga']=manifest
    record['physical']={'board_available':False,'board_programmed':False,'physical_boot_verified':False,
        'sky130_signoff_verified':False,'tapeout_submitted':False,'fabricated':False,'reason':'User has no board/runner or fabrication project'}
    if args.tests:
        suites=list(ET.parse(args.tests).getroot().iter('testsuite'))
        record['tests']={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
        if not record['tests']['tests'] or record['tests']['failures'] or record['tests']['errors']:raise ValueError('Test suite incomplete/failed')
        record['tests']['xml_sha256']=digest(args.tests)
    (out/'report.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'report':str(out/'report.json'),'all_requested_requirements_complete':False,'real_proof_generated':record['zkvm']['real_proof_generated']}))


if __name__=='__main__':main()
