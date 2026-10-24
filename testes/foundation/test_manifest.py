import copy
import json
from pathlib import Path

import pytest

from omega_platform.manifest import artifact_record,verify


def test_artifact_tampering_missing_and_traversal_rejected(tmp_path):
    artifact=tmp_path/'native';artifact.write_bytes(b'original')
    record={'format':'omega-build-manifest-1','artifacts':artifact_record([artifact],tmp_path)}
    assert verify(record,tmp_path)
    artifact.write_bytes(b'changed')
    with pytest.raises(ValueError,match='integrity'):verify(record,tmp_path)
    artifact.unlink()
    with pytest.raises(ValueError,match='Missing'):verify(record,tmp_path)
    record['artifacts']={'../outside':{'sha256':'0'*64,'bytes':1}}
    with pytest.raises(ValueError,match='escaping'):verify(record,tmp_path)
