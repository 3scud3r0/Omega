import argparse
import json
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(prog='omega cognition')
    parser.add_argument('action',choices=['discover','distill','schedule','qpu','trace','replay','memory','standalone'])
    parser.add_argument('--mode',choices=['strict','empirical','dream','creative','bicameral'],default='strict')
    parser.add_argument('--cases',type=int)
    parser.add_argument('--epsilon',default='0.00001');parser.add_argument('--alpha',default='0.05')
    parser.add_argument('--cycles',type=int,default=1);parser.add_argument('--proposals',type=int,default=4)
    parser.add_argument('--iterations',type=int,default=256);parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--temperature',type=float,default=2.0);parser.add_argument('--guide',choices=['heuristic','neural'],default='heuristic')
    parser.add_argument('--max-total-trials',type=int,default=2000000)
    parser.add_argument('--wall-seconds',type=int,default=300)
    parser.add_argument('--bft-local',action='store_true')
    parser.add_argument('--no-native',action='store_true')
    parser.add_argument('--zk-prover');parser.add_argument('--zk-verifier')
    parser.add_argument('spec',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if args.spec.stat().st_size>128*1024:parser.error('Specification byte budget')
    spec=json.loads(args.spec.read_text())
    if args.action=='discover':
        if args.output is None:parser.error('discover requires a fresh --output directory')
        from .bicameral import run,Options
        config=Options(mode=args.mode,cases=args.cases,epsilon=args.epsilon,alpha=args.alpha,cycles=args.cycles,
            proposals=args.proposals,iterations=args.iterations,seed=args.seed,temperature=args.temperature,guide=args.guide,
            max_total_trials=args.max_total_trials,wall_seconds=args.wall_seconds,bft=args.bft_local,native=not args.no_native,
            zk_prover=args.zk_prover,zk_verifier=args.zk_verifier)
        result=run(spec,args.output,options=config)
    elif args.mode!='strict':parser.error('Cognitive operation modes apply to discover')
    elif args.action=='distill':
        from .pipeline import distill
        result=distill(spec['intent'],spec['specification'],args.output,**spec.get('limits',{}))
    elif args.action=='schedule':
        from .scheduler import FairScheduler
        result=FairScheduler(spec['tasks'],max_wait=spec.get('max_wait',8)).run()
    elif args.action=='qpu':
        from .qpu import execute
        result=execute(spec['op'],spec['a'],spec['b'],bits=spec.get('bits',16),max_denominator=spec.get('max_denominator'))
    elif args.action=='memory':
        from .memory import plan_buffers
        result=plan_buffers(spec)
    elif args.action=='standalone':
        from .standalone import export
        result=export(spec['checkpoint'],spec['architecture'],args.output,input_bounds=spec['input_bounds'],output_bounds=spec['output_bounds'],input_scale=spec.get('input_scale',1))
    else:
        from .glass import certify_trace,replay
        result=replay(spec) if args.action=='replay' else certify_trace(spec['graph'],spec['inputs'])
    print(json.dumps(result,sort_keys=True,indent=2));return 0
