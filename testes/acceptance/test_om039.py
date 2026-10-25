"""OM-039: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_security.encoding import canonical,decode
from omega_selfhost.proof_protocol import envelope,encode

def test_unicode_canonicalization_and_malformed_signed_data():
    assert decode(canonical({'ação':['é',1]}))=={'ação':['é',1]}
    with pytest.raises(ValueError):decode(b'{"a":1,"a":2}')
    with pytest.raises(ValueError):canonical(['x'*8]*100,max_bytes=64)
    with pytest.raises(ValueError):decode(b'{"x":NaN}')

def test_envelope_binds_statement_and_dependency_order():
    a=envelope({'P':1},'proof','lean',['b','a','a'])
    b=envelope({'P':1},'proof','lean',['a','b'])
    assert encode(a)==encode(b) and a['statement_sha256']!=envelope({'P':2},'proof','lean',[])['statement_sha256']
