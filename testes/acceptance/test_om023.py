"""OM-023: executable checks; source delivery, not a recorded pass."""
from omega_selfhost.native_backend import compare
import pytest

def test_native_levels_produce_identical_checked_results(tmp_path):
    source=tmp_path/'program.omega';source.write_text('parametro x=3;perda l=x*x;gradiente l em x;mostrar l;')
    records=compare(source,tmp_path/'builds',levels=('-O0','-O2'))
    assert len(records)==2 and records[0]['signature']==records[1]['signature']
    assert all(r['admission']['valid'] for r in records)

def test_unrecognized_compiler_flag_is_rejected_before_build(tmp_path):
    from omega_selfhost.native_backend import build
    with pytest.raises(ValueError):build(tmp_path/'missing',tmp_path/'out',level='-fplugin=evil')
