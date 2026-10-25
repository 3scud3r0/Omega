"""Bounded JSON-schema subset for tool boundaries. No implicit coercion."""
from dataclasses import dataclass
import math
@dataclass(frozen=True)
class Contract:
    fields: dict
    required: frozenset[str]
    max_bytes: int=1024*1024
    def check(self,value):
        import json
        if type(value) is not dict or not self.required<=set(value)<=set(self.fields):raise ValueError('Tool fields do not match contract')
        if len(json.dumps(value,allow_nan=False).encode())>self.max_bytes:raise ValueError('Tool payload budget exceeded')
        for name,item in value.items():
            expected=self.fields[name]
            if type(item) is not expected:raise TypeError('Tool field type mismatch: '+name)
        return value
@dataclass(frozen=True)
class Tool:
    name: str
    action: str
    arguments: Contract
    response: Contract
    invoke: object
