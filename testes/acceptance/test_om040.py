"""OM-040: executable checks; source delivery, not a recorded pass."""
import hashlib
import pytest
from omega_platform.artifact_verifier import ArtifactVerifier

def test_independent_artifact_bytes_are_rechecked(tmp_path):
    file=tmp_path/'program';file.write_bytes(b'compiled')
    verifier=ArtifactVerifier(tmp_path);expected=hashlib.sha256(b'compiled').hexdigest()
    assert verifier.compare('program',expected)==file
    file.write_bytes(b'tampered')
    with pytest.raises(ValueError):verifier.compare('program',expected)
    with pytest.raises(ValueError):verifier.compare('..',expected)
