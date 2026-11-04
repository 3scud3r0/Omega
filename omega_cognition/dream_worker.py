"""Untrusted proposal worker. No Lean, oracle, ledger, compiler or activation."""
import sys,json,math
from pathlib import Path
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from omega_synth_mcts.search import search
from omega_synth_mcts.policy import HeuristicPolicy,NeuralPolicy
from omega_synth_mcts.grammar import Grammar


class Tempered:
    def __init__(self,guide,temperature):self.guide=guide;self.temperature=temperature
    def priors(self,partial,options,variables):
        raw=self.guide.priors(partial,options,variables)
        if any(not math.isfinite(v) or v<0 for v in raw):raise ValueError('Nonfinite proposal prior')
        values=[max(x,1e-12)**(1/self.temperature) for x in raw];total=sum(values)
        return [x/total for x in values]
    def update(self,labels,reward):self.guide.update(labels,reward)


def main():
    p=Path(sys.argv[1])
    if p.stat().st_size>1024**2:raise ValueError('Proposal input budget')
    data=json.loads(p.read_text());spec=data['spec'];limits=data['limits']
    guide=HeuristicPolicy()
    if data['guide']=='neural':
        sys.path.extend(data['python_paths'])
        grammar=Grammar(spec['variables'],spec['constants'],operators=spec['operators'])
        guide=NeuralPolicy([n for n,_ in grammar.productions(('hole',))],seed=limits['seed'])
    result=search(spec,verify=False,policy=Tempered(guide,data['temperature']),**limits)
    candidate=result.get('candidate') or result.get('best_observed')
    print(json.dumps({'candidate':candidate,'verified':False,'evaluations':result['evaluations'],'guide':data['guide'],'temperature':data['temperature']},sort_keys=True))


if __name__=='__main__':main()
