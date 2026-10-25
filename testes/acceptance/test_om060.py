"""OM-060: executable checks; source delivery, not a recorded pass."""
import ast,hashlib
import pytest
from omega_coder.ast_editor import replace_node

def test_ast_edit_preserves_unrelated_unicode_bytes_and_detects_stale_source():
    source='# ação\ndef f():\n    return 1\n\nkept=9\n';node=ast.parse(source).body[0].body[0].value
    sha=hashlib.sha256(source.encode()).hexdigest()
    assert replace_node(source,node,'2',sha)==source.replace('return 1','return 2')
    with pytest.raises(ValueError):replace_node(source+'# changed',node,'2',sha)
