"""OM-048: executable checks; source delivery, not a recorded pass."""
from omega_agent.consistency import contradictions,missing_premises
from omega_agent.inference import Rule

def test_contradiction_contains_both_evidence_sources():
    conflicts=contradictions([('P','e1'),('~P','e2'),('Q','e3')])
    assert len(conflicts)==1 and conflicts[0].positive==('e1',) and conflicts[0].negative==('e2',)
    assert missing_premises(Rule('r',frozenset(['P','Z']),'R'),['P'])==('Z',)
