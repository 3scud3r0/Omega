"""Host-owned immutable transition policies, not prompts for the proposer."""
from dataclasses import dataclass
import json
from omega_refine_check.syntax import parse,identifier
from omega_selfhost.proof_protocol import encode
import hashlib


@dataclass(frozen=True)
class Policy:
    encoded:bytes
    def __init__(self,data):
        fields={'id','version','state','actions'}
        if type(data) is not dict or set(data)!=fields or type(data['version']) is not int or data['version']<1:raise ValueError('Explicit versioned action policy required')
        identifier(data['id'])
        if type(data['state']) is not dict or not 1<=len(data['state'])<=32 or type(data['actions']) is not dict or not 1<=len(data['actions'])<=32:raise ValueError('Policy cardinality budget exceeded')
        for name,predicate in data['state'].items():identifier(name);parse(predicate)
        for name,action in data['actions'].items():
            identifier(name)
            if type(action) is not dict or set(action)!={'parameters','requires','updates','effect'}:raise ValueError('Unknown action policy fields')
            identifier(action['effect'])
            if type(action['parameters']) is not dict or len(action['parameters'])>16 or set(action['parameters'])&set(data['state']):raise ValueError('Invalid or shadowing action parameters')
            for var,predicate in action['parameters'].items():identifier(var);parse(predicate)
            if type(action['requires']) is not list or len(action['requires'])>32:raise ValueError('Bounded preconditions required')
            for predicate in action['requires']:parse(predicate)
            if set(action['updates'])!=set(data['state']):raise ValueError('Every state coordinate must have an explicit simultaneous update')
            for expr in action['updates'].values():parse(expr)
        raw=encode(data)
        if len(raw)>65536:raise ValueError('Policy byte budget exceeded')
        object.__setattr__(self,'encoded',raw)
    @property
    def data(self):return json.loads(self.encoded)
    @property
    def sha256(self):return hashlib.sha256(self.encoded).hexdigest()
