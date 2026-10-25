"""OM-050: executable checks; source delivery, not a recorded pass."""
from omega_agent.metacognition import decide,Decision

def test_metacognition_requests_evidence_help_and_bounded_stop():
    args={'remaining':3,'contradictions':False,'unknown_domain':False,'expected_gain':2,'cost':1}
    assert decide(**args)==Decision.CONTINUE
    assert decide(**{**args,'contradictions':True})==Decision.EVIDENCE
    assert decide(**{**args,'unknown_domain':True})==Decision.HELP
    assert decide(**{**args,'remaining':0})==Decision.STOP
