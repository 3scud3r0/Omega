"""OM-119: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_tools.vision import describe

def test_vision_provider_contract_preserves_input_hash_and_untrusted_label(signed_authority):
    verifier,mint=signed_authority
    result=describe(b'fixture-image',lambda request:{'description':'box','objects':[{'label':'box','confidence':.9,'box':[0,0,1,1]}]},capability=mint(['vision.infer']),verifier=verifier,principal='agent')
    assert result['description']=='box' and len(result['source_sha256'])==64 and result['authority'] is False
    with pytest.raises(ValueError):describe(b'image',lambda request:{'unexpected':1},capability=mint(['vision.infer']),verifier=verifier,principal='agent')
