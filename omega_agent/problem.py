"""Data-only problem contracts; success must be decided by an external evaluator."""
from dataclasses import dataclass,field
import hashlib,json
@dataclass(frozen=True)
class Problem:
    id: str
    domain: str
    inputs: dict
    constraints: tuple[str,...]
    success_contract: str
    def __post_init__(self):
        if not self.id or not self.domain or not self.success_contract:raise ValueError('Incomplete problem')
        encoded=json.dumps(self.inputs,sort_keys=True,allow_nan=False)
        if len(encoded)>1024*1024 or len(self.constraints)>256:raise ValueError('Problem budget exceeded')
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.__dict__,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
@dataclass(frozen=True)
class Goal:
    problem_id: str
    objective: str
    authorized_by: str
    max_actions: int=100
    def __post_init__(self):
        if not self.problem_id or not self.objective or not self.authorized_by or not 0<self.max_actions<=10000:raise ValueError('Invalid authorized goal')
