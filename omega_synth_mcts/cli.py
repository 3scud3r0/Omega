import argparse,json
from pathlib import Path
from .search import synthesize

def main(argv=None):
    parser=argparse.ArgumentParser(prog='omega synth')
    parser.add_argument('spec',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--iterations',type=int,default=1024);parser.add_argument('--max-nodes',type=int,default=15)
    parser.add_argument('--seconds',type=float,default=30);parser.add_argument('--seed',type=int,default=0)
    args=parser.parse_args(argv)
    result=synthesize(json.loads(args.spec.read_text()),args.output,iterations=args.iterations,max_nodes=args.max_nodes,seconds=args.seconds,seed=args.seed)
    print(json.dumps(result,sort_keys=True,indent=2));return 0 if result['verified'] else 1
