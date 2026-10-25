"""OM-072: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_memory.retrieval import HybridIndex

def test_hybrid_retrieval_ranks_relevant_document_and_keeps_provenance():
    index=HybridIndex(2)
    index.add('math','exact rational arithmetic',[1,0],['proof'])
    index.add('food','bread recipe',[0,1],['recipe'])
    result=index.search('rational',[1,0],k=1)
    assert result[0]['id']=='math' and result[0]['evidence']==('proof',)
    with pytest.raises(ValueError):index.search('x',[1],k=1)
