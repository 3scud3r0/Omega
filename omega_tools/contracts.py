"""Bounded JSON-schema subset for tool boundaries. No implicit coercion."""
from dataclasses import dataclass
from types import MappingProxyType
from omega_security.encoding import canonical,snapshot
@dataclass(frozen=True)
class Contract:
    fields: dict
    required: frozenset[str]
    max_bytes: int=1024*1024
    def __post_init__(self):
        allowed={str,int,float,bool,list,dict,type(None)}
        if type(self.fields) is not dict or any(type(k) is not str or not k or v not in allowed for k,v in self.fields.items()):raise ValueError('Invalid tool schema')
        required=frozenset(self.required)
        if not required<=set(self.fields) or type(self.max_bytes) is not int or not 1<=self.max_bytes<=8*1024**2:raise ValueError('Invalid contract bounds')
        object.__setattr__(self,'fields',MappingProxyType(dict(self.fields)))
        object.__setattr__(self,'required',required)
    def check(self,value):
        if type(value) is not dict or not self.required<=set(value)<=set(self.fields):raise ValueError('Tool fields do not match contract')
        canonical(value,max_bytes=self.max_bytes)
        for name,item in value.items():
            expected=self.fields[name]
            if type(item) is not expected:raise TypeError('Tool field type mismatch: '+name)
        return value
    def copy(self,value):return snapshot(self.check(value),max_bytes=self.max_bytes)
@dataclass(frozen=True)
class Tool:
    name: str
    action: str
    arguments: Contract
    response: Contract
    invoke: object
    path_fields: tuple[str,...]=()
    approval_required: bool=False
    def __post_init__(self):
        if type(self.name) is not str or not self.name or type(self.action) is not str or not self.action or not callable(self.invoke):raise ValueError('Invalid tool registration')
        if type(self.arguments) is not Contract or type(self.response) is not Contract:raise TypeError('Tool contracts required')
        if type(self.path_fields) is not tuple or len(set(self.path_fields))!=len(self.path_fields):raise ValueError('Invalid tool path fields')
        if any(self.arguments.fields.get(name) is not str or name not in self.arguments.required for name in self.path_fields):raise ValueError('Scoped paths must be required string fields')
        if type(self.approval_required) is not bool:raise TypeError('Explicit tool approval policy required')
        if self.action in {'file.write','code.write','database.write','git.write','github.pr.create','github.issue.create'} and not self.approval_required:
            raise ValueError('Mutating tool needs an independent approval gate')
