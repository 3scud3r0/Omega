import argparse
import json
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(prog='omega cognition')
    parser.add_argument('mode',choices=['distill','schedule','qpu','trace','replay','memory','standalone'])
    parser.add_argument('spec',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv);spec=json.loads(args.spec.read_text())
    if args.mode=='distill':
        from .pipeline import distill
        result=distill(spec['intent'],spec['specification'],args.output,**spec.get('limits',{}))
    elif args.mode=='schedule':
        from .scheduler import FairScheduler
        result=FairScheduler(spec['tasks'],max_wait=spec.get('max_wait',8)).run()
    elif args.mode=='qpu':
        from .qpu import execute
        result=execute(spec['op'],spec['a'],spec['b'],bits=spec.get('bits',16),max_denominator=spec.get('max_denominator'))
    elif args.mode=='memory':
        from .memory import plan_buffers
        result=plan_buffers(spec)
    elif args.mode=='standalone':
        from .standalone import export
        result=export(spec['checkpoint'],spec['architecture'],args.output,input_bounds=spec['input_bounds'],output_bounds=spec['output_bounds'],input_scale=spec.get('input_scale',1))
    else:
        from .glass import certify_trace,replay
        result=replay(spec) if args.mode=='replay' else certify_trace(spec['graph'],spec['inputs'])
    print(json.dumps(result,sort_keys=True,indent=2));return 0
