"""Bounded, reproducible frontier tasks and an empirical repertoire ledger."""
from fractions import Fraction as Q
import hashlib
import json
import math
from pathlib import Path
import random
import time
from omega_selfhost.proof_protocol import encode


class CuriosityEngine:
    def __init__(self,seed=0):
        if type(seed) is not int or not 0<=seed<2**64:raise ValueError('Bounded curiosity seed required')
        self.seed=seed;self.rng=random.Random(seed);self.history={}
    def task(self,family=None):
        families=('affine','polynomial','bounded-control','diophantine-instance','compiler-identity')
        family=family or min(families,key=lambda x:(self.history.get(x,{}).get('attempts',0),self.rng.random()))
        if family not in families:raise ValueError('Unknown bounded curiosity family')
        a=self.rng.choice((1,2,3));b=self.rng.choice((0,1,2))
        if family=='diophantine-instance':
            solution=self.rng.choice((0,1,2));rhs=a*solution+b
            spec={'variables':{},'constants':[0,1,2,3],'operators':['+','-','*'],
                  'ensures':f'{a}*result+{b} == {rhs}',
                  'examples':[{'inputs':{},'output':str(solution)}]};bounds=[];limits=[-16,16]
        else:
            coefficient=self.rng.randint(2,65535) if family=='compiler-identity' else 2
            expression=f'{a}*x+{b}' if family=='affine' else 'x*x' if family=='polynomial' else f'(x*{coefficient})-x*{coefficient-1}' if family=='compiler-identity' else 'relu(x)'
            from omega_refine_check.syntax import parse,evaluate
            examples=[{'inputs':{'x':str(x)},'output':str(evaluate(parse(expression),{'x':Q(x)}))} for x in (-1,0,1)]
            spec={'variables':{'x':'self>=-1 and self<=1'},'constants':[0,1,2,3],
                  'operators':['+','-','*','neg','relu'],'ensures':'result == '+expression,'examples':examples}
            bounds=[[-1,1]];limits=[-4,5]
        identity=hashlib.sha256(encode({'family':family,'spec':spec})).hexdigest()
        task={'id':identity,'family':family,'spec':spec,'input_bounds':bounds,'output_bounds':limits}
        if family=='compiler-identity':task['lhs']=expression
        return task
    def observe(self,task,accepted):
        record=self.history.setdefault(task['family'],{'attempts':0,'accepted':0})
        record['attempts']+=1;record['accepted']+=int(bool(accepted))
        # Empirical Bernoulli uncertainty is a scheduling heuristic, not a
        # measure of logical truth or a proof of mathematical novelty.
        entropy=0.0
        for value in self.history.values():
            p=(value['accepted']+1)/(value['attempts']+2)
            entropy+=-p*math.log2(p)-(1-p)*math.log2(1-p)
        return {'history':json.loads(json.dumps(self.history)),'empirical_uncertainty_bits':entropy}
