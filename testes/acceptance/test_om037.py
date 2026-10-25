"""OM-037: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_selfhost.proof_protocol import envelope
from omega_selfhost.statement_binding import verify

def test_statement_binding_rejects_irrelevant_valid_certificate():
    proof=envelope({'claim':'P'},'certificate','kernel',['d'])
    assert verify({'claim':'P'},proof,lambda *_:True,checker_id='kernel',dependencies=['d'])
    with pytest.raises(ValueError):verify({'claim':'Q'},proof,lambda *_:True,checker_id='kernel',dependencies=['d'])
    with pytest.raises(ValueError):verify({'claim':'P'},proof,lambda *_:True,checker_id='other',dependencies=['d'])
