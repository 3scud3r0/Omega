from dataclasses import dataclass
@dataclass(frozen=True)
class Conflict:
    atom: str
    positive: tuple[str,...]
    negative: tuple[str,...]
def contradictions(assertions):
    positive={};negative={}
    for assertion,evidence in assertions:
        target=negative if assertion.startswith('~') else positive
        atom=assertion[1:] if assertion.startswith('~') else assertion
        target.setdefault(atom,[]).append(evidence)
    return tuple(Conflict(a,tuple(positive[a]),tuple(negative[a])) for a in sorted(positive.keys()&negative.keys()))
def missing_premises(rule,facts):return tuple(sorted(set(rule.premises)-set(facts)))
