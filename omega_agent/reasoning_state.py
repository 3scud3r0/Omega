"""Explicit logical premises/evidence, not an opaque claim of proof."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Step:
    id: str
    premises: tuple[str,...]
    conclusion: str
    evidence: tuple[str,...]
    confidence: float
    def __post_init__(self):
        if not self.id or not self.conclusion or not 0<=self.confidence<=1:raise ValueError('Invalid reasoning record')
class ReasoningState:
    def __init__(self,assumptions=()):self.assumptions=frozenset(assumptions);self.steps={}
    def add(self,step):
        if type(step) is not Step or step.id in self.steps:raise ValueError('Duplicate/invalid step')
        if any(p not in self.steps and p not in self.assumptions for p in step.premises):raise ValueError('Missing premise')
        if len(self.steps)>=10000:raise ValueError('Reasoning record budget exceeded')
        self.steps[step.id]=step
    def provenance(self,id):
        seen=set();pending=[id]
        while pending:
            name=pending.pop()
            if name in seen:continue
            seen.add(name)
            if name in self.steps:pending.extend(self.steps[name].premises)
            elif name not in self.assumptions:raise KeyError(name)
        return tuple(sorted(seen))
