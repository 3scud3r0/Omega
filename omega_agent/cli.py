"""Data-only entry points for finite reasoning, plans and scalar synthesis."""
import argparse,json,sys
from pathlib import Path
from fractions import Fraction
from omega_platform.results import attempt,Err

def solve(mode,data,max_candidates=10000,max_size=7):
    if type(data) is not dict:raise ValueError('JSON object problem required')
    if mode=='infer':
        from .inference import Rule,derive
        rules=tuple(Rule(r['id'],frozenset(r['premises']),r['conclusion']) for r in data['rules'])
        known,proof=derive(data['facts'],rules,fuel=max_candidates)
        return {'domain':'propositional_horn','facts':sorted(known),'derivations':proof}
    if mode=='plan':
        from .hierarchical_planner import Task,Plan
        tasks=tuple(Task(t['id'],t['description'],tuple(t.get('dependencies',())),t.get('priority',0)) for t in data['tasks'])
        plan=Plan(tasks)
        return {'order':plan.order(),'ready':plan.ready(data.get('completed',()))}
    if mode=='synthesize':
        from omega_coder.contract_synthesis import synthesize
        examples=tuple((e['inputs'],e['output']) for e in data['examples'])
        result=synthesize(data['variables'],data.get('constants',[0,1]),examples,max_nodes=max_size,max_candidates=max_candidates)
        return {'candidate':result,'domain':'finite rational arithmetic examples','universal_proof':False}
    raise ValueError('Unknown finite agent mode')

def main(argv=None):
    parser=argparse.ArgumentParser(prog='omega agent')
    parser.add_argument('mode',choices=['infer','plan','synthesize'])
    parser.add_argument('problem',type=Path)
    parser.add_argument('--max-candidates',type=int,default=10000)
    parser.add_argument('--max-size',type=int,default=7)
    args=parser.parse_args(argv)
    def operation():
        if not 1<=args.max_candidates<=100000 or not 1<=args.max_size<=31:raise ValueError('Invalid finite reasoning budget')
        with args.problem.open('rb') as stream:data=stream.read(1024*1024+1)
        if len(data)>1024*1024:raise ValueError('Problem byte budget exceeded')
        return solve(args.mode,json.loads(data),args.max_candidates,args.max_size)
    result=attempt('agent',operation)
    def encode(value):
        if isinstance(value,Fraction):return str(value)
        raise TypeError('Unsupported agent result field')
    if isinstance(result,Err):
        print(json.dumps(result.to_dict(),ensure_ascii=False),file=sys.stderr);return 1
    print(json.dumps(result.to_dict(),ensure_ascii=False,default=encode));return 0
