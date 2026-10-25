"""OM-056: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_coder.repository_index import index

def test_repository_index_records_symbols_imports_calls_and_ignores_symlinks(tmp_path):
    (tmp_path/'a.py').write_text('import math\ndef f(x):\n    return math.sqrt(x)\n')
    (tmp_path/'link.py').symlink_to(tmp_path/'a.py')
    result=index(tmp_path)
    assert set(result)=={'a.py'} and result['a.py']['symbols'][0]['name']=='f'
    assert result['a.py']['calls'][0]['callee']=='math.sqrt' and result['a.py']['imports']==['math']
    with pytest.raises(ValueError):index(tmp_path,max_bytes=1)
