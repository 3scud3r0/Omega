"""OM-150: executable checks; source delivery, not a recorded pass."""
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from omega_security.signatures import SignatureVerifier
from omega_security.encoding import canonical
from omega_bench.reproduction import ReproductionGate,ExternalReview

def test_external_review_requires_independent_signature_and_exact_artifacts():
    private=Ed25519PrivateKey.generate();public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    signatures=SignatureVerifier({'external':public})
    gate=ReproductionGate(['author'],['external'],signatures.record)
    value={'reviewer':'external','artifact_sha256':'a'*64,'experiment_sha256':'b'*64,'outcome':'reproduced'}
    review=ExternalReview(**value,signature=private.sign(canonical(value)))
    assert gate.accept(review,'a'*64,'b'*64)['reproduced'] is True
    with pytest.raises(ValueError):gate.accept(review,'c'*64,'b'*64)
    forged=ExternalReview(**value,signature=b'x'*64)
    with pytest.raises(PermissionError):gate.accept(forged,'a'*64,'b'*64)
