"""OM-073: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_memory.knowledge import Claim,KnowledgeBase

def test_claims_merge_evidence_and_conflicts_retain_both_values():
    knowledge=KnowledgeBase();id=knowledge.add(Claim('x','is','A',('e1',)))
    assert knowledge.add(Claim('x','is','A',('e2',)))==id
    assert knowledge.query('x','is')[0].evidence==('e1','e2')
    knowledge.add(Claim('x','is','B',('e3',)))
    assert len(knowledge.conflicts()[('x','is')])==2
    with pytest.raises(ValueError):Claim('x','is','A',())
