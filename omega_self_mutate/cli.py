import argparse,json
from pathlib import Path
from .rules import discover_rule
from .bootstrap import evolve
from .activation import activate,deactivate
from .profiler import profile_native

def main(argv=None):
    parser=argparse.ArgumentParser(prog='omega mutate')
    parser.add_argument('mode',choices=['discover','evolve','activate','deactivate','profile'])
    parser.add_argument('--lhs',default='(x*2)-x');parser.add_argument('--output',type=Path)
    parser.add_argument('--source',type=Path);parser.add_argument('--activate',action='store_true')
    args=parser.parse_args(argv)
    if args.mode=='deactivate':deactivate();result={'active':False}
    elif args.mode=='activate':result=activate(args.output)
    elif args.mode=='profile':result=profile_native(args.source)
    else:
        rule=discover_rule(args.lhs)
        result=rule if args.mode=='discover' else evolve(rule,args.output,activate_default=args.activate)
    print(json.dumps(result,sort_keys=True,indent=2));return 0
