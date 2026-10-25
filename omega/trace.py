"""Deterministic pure-graph trace; input must already have validated TypedIR."""
from dataclasses import dataclass
from fractions import Fraction
from .typed_ir import TypedIR
from .motor_v1 import MaquinaV1,num
@dataclass(frozen=True)
class Frame:
    index: int
    operator: str
    shape: tuple[int,...]
    value: object
    def to_dict(self):return {'index':self.index,'operator':self.operator,'shape':list(self.shape),'value':self.value}
def evaluate(ir,state):
    if type(ir) is not TypedIR:raise TypeError('Validated TypedIR required')
    graph=ir.legacy();machine=MaquinaV1(graph)
    if set(state)!={p['nome'] for p in graph['parametros']}:raise ValueError('Parameter set mismatch')
    from .nucleo_v1 import formato
    for p in graph['parametros']:
        if formato(state[p['nome']])!=tuple(graph['nos'][p['id']]['forma']):raise ValueError('State shape mismatch')
    values=machine.frente(estado=state)
    return tuple(Frame(i,node['op'],tuple(node['forma']),num(value)) for i,(node,value) in enumerate(zip(graph['nos'],values)))
