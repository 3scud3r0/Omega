"""Explicit split by composition signature, not random reuse of trained combinations."""
from itertools import product
def split(primitives,arity,training_signatures,limit=10000):
    primitives=tuple(sorted(set(primitives)));training=set(tuple(s) for s in training_signatures)
    if not 1<=arity<=8 or len(primitives)**arity>limit:raise ValueError('Composition budget exceeded')
    train=[];held=[]
    for signature in product(primitives,repeat=arity):(train if signature in training else held).append(signature)
    return tuple(train),tuple(held)
def evaluate(signatures,solve,verify):
    observations=[]
    for signature in signatures:
        candidate=solve(signature);result=verify(signature,candidate)
        if type(result) is not bool:raise TypeError('Independent boolean verifier required')
        observations.append({'signature':signature,'correct':result})
    return tuple(observations)
