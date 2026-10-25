"""OM-059: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_coder.generation import generate,Candidate

@pytest.mark.parametrize('language',['omega','python','c','lean'])
def test_source_candidates_are_bounded_deduplicated_and_tagged(language):
    results=generate('spec',lambda *_:iter(['source A','source A','source B']),language,limit=2)
    assert [r.source for r in results]==['source A','source B']
    assert all(r.language==language for r in results)

def test_unsupported_language_rejected():
    with pytest.raises(ValueError):Candidate('shell','rm -rf /','provider')
