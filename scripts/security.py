#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from omega_platform.security import validate

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=ROOT/'artifacts/foundation/security.json')
parser.add_argument('--mutations',type=int,default=48)
args=parser.parse_args()
if not 1<=args.mutations<=10000:parser.error('mutations must be between 1 and 10000')
report=validate(ROOT,count=args.mutations)
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(f"Native security: {report['passed']} passed; {report['failed']} failed. {args.output}")
raise SystemExit(0 if report['valid'] else 1)
