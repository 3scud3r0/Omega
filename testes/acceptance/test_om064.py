"""OM-064: executable checks; source delivery, not a recorded pass."""
from omega_coder.contract_synthesis import synthesize

def test_finite_synthesis_finds_valid_rational_expression_without_universal_claim():
    result=synthesize(['x'],[0,1],[({'x':1},2),({'x':2},3)],max_nodes=3,max_candidates=100)
    assert result is not None and result['universal'] is False and result['checked']<=100
    assert synthesize(['x'],[0],[({'x':0},999)],max_nodes=1,max_candidates=2) is None
