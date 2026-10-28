import argparse
import json
from pathlib import Path
from .contracts import check_program
from .compiler import build,audit


def main(argv=None):
    parser=argparse.ArgumentParser(prog='omega refine')
    parser.add_argument('mode',choices=['check','build','audit']);parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if args.mode=='check':result=check_program(args.source.read_text())
    elif args.output is None:parser.error('--output is required')
    elif args.mode=='build':result=build(args.source,args.output)
    else:result=audit(args.source,args.output)
    print(json.dumps(result,sort_keys=True,indent=2));return 0
