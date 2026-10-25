"""Product red-team runner. Cases are untrusted inputs, never authority changes."""
from dataclasses import dataclass
@dataclass(frozen=True)
class AttackCase:
    id: str
    vector: str
    payload: object
    expected_policy: str
class IndependentAssessment:
    def __init__(self,developer_ids,assessor):self.developer_ids=frozenset(developer_ids);self.assessor=assessor
    def run(self,cases,target,judge,limit=256):
        results=[]
        for case in cases:
            if len(results)>=limit:raise ValueError('Adversarial budget exceeded')
            if case.id in self.developer_ids:raise ValueError('Adversarial assessment is contaminated')
            response=target(case.payload);decision=judge(case,response)
            if type(decision) is not bool:raise ValueError('Independent policy judgment required')
            results.append({'case':case.id,'vector':case.vector,'policy_respected':decision,'assessor':self.assessor})
        return tuple(results)
