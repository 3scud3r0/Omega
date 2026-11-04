#!/usr/bin/env python3
"""Produce reviewable binaries, proof, bitstream, logs and real test receipts."""
from pathlib import Path
import argparse
from dataclasses import asdict
from hashlib import sha256,sha3_256
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from omega_sovereign.native import build_seed,build_crypto
from omega_sovereign.baremetal import build as build_boot
from omega_sovereign.hardware import fpga,tool,digest
from omega_sovereign.air_fri import prove,verify,canonical
from omega_platform.sandbox import run,trusted
from omega_platform.budget import COMPILER_BUDGET,BUILD_BUDGET,Budget


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists():raise FileExistsError('Fresh evidence destination required')
    out.mkdir(parents=True)
    report={'format':'omega-sovereign-evidence-1','all_six_requirements_complete':False,
            'physical_hardware_validated':False,'production_crypto_approved':False,'zero_knowledge':False}
    paths=[]
    for directory in ('omega_sovereign','sovereign','hardware/sovereign','testes/sovereign'):
        paths += [p for p in (ROOT/directory).rglob('*') if p.suffix in ('.py','.S','.omega','.v','.pcf','.json')]
    paths += [ROOT/'formal/Sovereign.lean',ROOT/'formal/tensor/lakefile.lean',Path(__file__).resolve(),ROOT/'requirements/sovereign-tools.json']
    report['inputs']={str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)}
    report['input_tree_sha256']=sha256(canonical(report['inputs'])).hexdigest()
    report['native']=build_seed(out/'omegac-rv64');report['crypto']=build_crypto(out/'crypto-rv64')
    report['boot']=build_boot(out/'boot.elf');qemu=tool('qemu-riscv64')
    source=out/'example.omega';source.write_text('mostrar (123456789012345678901234567890/3+1)*-2;\nmostrar 1/7+2/7;\n')
    compile_result=run([qemu,out/'omegac-rv64',source,out/'example.elf'],readonly=[out/'omegac-rv64'],writable=[out],threads=True,budget=COMPILER_BUDGET)
    report['native_compile']=asdict(compile_result)
    if not compile_result.ok:raise RuntimeError('Native compilation failed')
    execution=run([qemu,out/'example.elf'],readonly=[out/'example.elf'],threads=True,budget=COMPILER_BUDGET)
    report['native_execution']=asdict(execution)
    if not execution.ok or execution.stdout!='-82304526008230452600823045262/1\n3/7\n':raise RuntimeError('Native result mismatch')
    disk=out/'cas.raw';disk.write_bytes(bytes(512*1024))
    prefix=ROOT.parent/'.tools/sovereign/usr/lib/x86_64-linux-gnu'
    if prefix.is_dir():os.environ['LD_LIBRARY_PATH']=str(prefix)
    boot=trusted([tool('qemu-system-riscv64'),'-machine','virt','-m','128M','-smp','1','-bios','none',
                  '-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot',
                  '-kernel',str(out/'boot.elf'),'-global','virtio-mmio.force-legacy=false',
                  '-drive',f'file={disk},format=raw,if=none,id=d','-device','virtio-blk-device,drive=d'],
                 budget=Budget(wall_seconds=10,memory_bytes=2*1024**3))
    report['baremetal_execution']=asdict(boot)
    if not boot.ok or 'OMEGA BAREMETAL PASS' not in boot.stdout:raise RuntimeError('Baremetal validation failed')
    data=disk.read_bytes()
    if data[1024:1056]!=sha3_256(data[512:1024]).digest():raise RuntimeError('Guest CAS digest mismatch')
    report['fpga']=fpga(out/'fpga')
    started=time.monotonic();proof=prove(3,5,32);proving=time.monotonic()-started
    started=time.monotonic();valid=verify(proof,proof['statement']);verification=time.monotonic()-started
    (out/'air-proof.json').write_bytes(canonical(proof));(out/'air-statement.json').write_bytes(canonical(proof['statement']))
    report['air_fri']={'valid':valid,'bytes':len(canonical(proof)),'prove_seconds':proving,'verify_seconds':verification,
                       'machine':'x[i+1]=x[i]^2+c mod Goldilocks','steps':32,'queries':32,'zero_knowledge':False}
    if not valid:raise RuntimeError('AIR/FRI verification failed')
    tests=trusted([sys.executable,'-m','pytest','testes/sovereign','-q',f'--junitxml={out}/tests.xml'],cwd=ROOT,budget=BUILD_BUDGET)
    (out/'tests.log').write_text(tests.stdout+tests.stderr)
    report['test_command']=asdict(tests)
    if (out/'tests.xml').is_file():
        xml=ET.parse(out/'tests.xml').getroot()
        report['tests']={key:sum(int(suite.attrib.get(key,0)) for suite in xml.iter('testsuite')) for key in ('tests','failures','errors','skipped')}
    report['artifacts']={str(p.relative_to(out)):digest(p) for p in sorted(out.rglob('*')) if p.is_file()}
    report['validation_passed']=tests.ok
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':str(out/'report.json'),'passed':tests.ok,'tests':report.get('tests')},indent=2))
    return 0 if tests.ok else 1


if __name__=='__main__':raise SystemExit(main())
