"""Typed scalar expression enumeration, exact finite observation oracle."""
from fractions import Fraction
from itertools import product
def synthesize(variables,constants,examples,*,max_nodes=7,max_candidates=10000):
    variables=tuple(variables);constants=tuple(Fraction(c) for c in constants);examples=tuple(examples)
    if not examples or not 1<=max_nodes<=31:raise ValueError('Finite synthesis contract required')
    atoms=[('var',v) for v in variables]+[('const',c) for c in constants];levels={1:atoms};checked=0
    def evaluate(expr,env):
        if expr[0]=='var':return Fraction(env[expr[1]])
        if expr[0]=='const':return expr[1]
        a,b=evaluate(expr[1],env),evaluate(expr[2],env)
        return a+b if expr[0]=='+' else a-b if expr[0]=='-' else a*b
    for size in range(1,max_nodes+1):
        if size>1:
            levels[size]=[]
            for left in range(1,size-1):
                right=size-1-left
                for op,a,b in product(('+','-','*'),levels.get(left,()),levels.get(right,())):
                    if len(levels[size])+checked>=max_candidates:break
                    levels[size].append((op,a,b))
        for expression in levels.get(size,()):
            checked+=1
            if checked>max_candidates:return None
            if all(evaluate(expression,env)==Fraction(target) for env,target in examples):return {'expression':expression,'checked':checked,'universal':False}
    return None
