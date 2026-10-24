#!/usr/bin/env python3
"""Record/verify the packages, native stages and Lean kernels of this build."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from omega_platform.manifest import build_manifest,verify

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=ROOT/'artifacts/build-manifest.json')
parser.add_argument('--verify',type=Path)
args=parser.parse_args()
if args.verify:
    verify(json.loads(args.verify.read_text()),ROOT)
    print('Artifact integrity verified')
else:
    paths=[*sorted((ROOT/'build/selfhost').glob('omegac-stage*')),
           *sorted((ROOT/'dist').glob('linguagem_omega-*.whl')),
           *sorted((ROOT/'dist').glob('linguagem_omega-*.tar.gz')),
           ROOT/'formal/lean/.lake/build/bin/omega_kernel',
           ROOT/'formal/tensor/.lake/build/bin/omega_tensor_kernel']
    if not paths:raise SystemExit('No build artifacts found')
    record=build_manifest(ROOT,paths)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
    verify(record,ROOT)
    print(f'{len(paths)} artifacts recorded and verified: {args.output}')
