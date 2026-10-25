"""Data-only problem contracts; success must be decided by an external evaluator."""
from dataclasses import dataclass
from omega_security.encoding import canonical,decode,digest


def _text(value,limit=256):
    return type(value) is str and 0<len(value)<=limit and not any(ord(c)<32 for c in value)
@dataclass(frozen=True)
class Problem:
    id: str
    domain: str
    inputs: dict
    constraints: tuple[str,...]
    success_contract: str
    def __post_init__(self):
        if not _text(self.id) or not _text(self.domain) or type(self.success_contract) is not str or not 0<len(self.success_contract)<=16384:raise ValueError('Incomplete problem')
        if type(self.inputs) is not dict or type(self.constraints) is not tuple or len(self.constraints)>256 or any(type(c) is not str or len(c)>4096 for c in self.constraints):raise ValueError('Invalid problem constraints/input')
        canonical(self.to_dict())
    def to_dict(self):return {'id':self.id,'domain':self.domain,'inputs':self.inputs,'constraints':list(self.constraints),'success_contract':self.success_contract}
    def snapshot(self):return canonical(self.to_dict())
    def fingerprint(self):return digest(self.to_dict())
    @classmethod
    def from_snapshot(cls,data):
        value=decode(data)
        if type(value) is not dict or set(value)!={'id','domain','inputs','constraints','success_contract'} or type(value['constraints']) is not list:raise ValueError('Unknown problem schema')
        value['constraints']=tuple(value['constraints']);return cls(**value)
@dataclass(frozen=True)
class Goal:
    problem_id: str
    objective: str
    authorized_by: str
    max_actions: int=100
    def __post_init__(self):
        if not _text(self.problem_id) or type(self.objective) is not str or not 0<len(self.objective)<=16384 or not _text(self.authorized_by) or type(self.max_actions) is not int or not 0<self.max_actions<=10000:raise ValueError('Invalid authorized goal')
    def to_dict(self):return {'problem_id':self.problem_id,'objective':self.objective,'authorized_by':self.authorized_by,'max_actions':self.max_actions}
    def subject(self,problem_sha256):return digest({'format':'omega-authorized-goal-1','problem_sha256':problem_sha256,'goal':self.to_dict()})
