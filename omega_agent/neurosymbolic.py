"""Proposals are untrusted data until the independent checker accepts them."""
from dataclasses import dataclass
@dataclass(frozen=True)
class ProposalDecision:
    proposal: object
    accepted: bool
    certificate: object
    origin: str
def propose_and_check(problem,model,decode,checker,limit=32):
    if not 1<=limit<=256:raise ValueError('Invalid proposal budget')
    decisions=[]
    for proposal in model.propose(problem,limit):
        if len(decisions)>=limit:break
        obj=decode(proposal)
        result=checker(problem,obj)
        if type(result) is not dict or type(result.get('valid')) is not bool:raise ValueError('Checker protocol error')
        decisions.append(ProposalDecision(obj,result['valid'],result.get('certificate'),type(model).__name__))
    return tuple(decisions)
def feedback(decisions):return tuple({'proposal':d.proposal,'verified':d.accepted,'certificate':d.certificate} for d in decisions)
