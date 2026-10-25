"""OM-054: executable checks; source delivery, not a recorded pass."""
from omega_agent.compositional import split,evaluate

def test_unseen_compositions_are_disjoint_and_checked():
    train,held=split(['add','mul'],2,[('add','add')])
    assert train==( ('add','add'),) and len(held)==3 and not set(train)&set(held)
    results=evaluate(held,lambda signature:signature,lambda signature,candidate:signature==candidate)
    assert all(row['correct'] for row in results)
