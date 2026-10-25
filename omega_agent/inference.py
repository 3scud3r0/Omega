"""Finite propositional Horn inference, retaining derivation witnesses."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Rule:
    id: str
    premises: frozenset[str]
    conclusion: str
    def __post_init__(self):
        if not self.id or not self.conclusion or len(self.premises)>128:raise ValueError('Invalid rule')
def derive(facts,rules,*,fuel=10000):
    known=set(facts);proof={f:('assumption',()) for f in known};rules=tuple(sorted(rules,key=lambda r:r.id))
    if len(rules)>10000 or len(known)>10000:raise ValueError('Inference domain exceeded')
    changed=True
    while changed:
        changed=False
        for rule in rules:
            fuel-=1
            if fuel<0:raise ValueError('Inference fuel exhausted')
            if rule.conclusion not in known and rule.premises<=known:
                known.add(rule.conclusion);proof[rule.conclusion]=(rule.id,tuple(sorted(rule.premises)));changed=True
    return frozenset(known),proof
