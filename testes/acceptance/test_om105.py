"""OM-105: executable checks; source delivery, not a recorded pass."""
from omega_evolution.compiler_tuning import evaluate

def test_compiler_tuning_checks_native_semantics_before_selection(tmp_path):
    source=tmp_path/'program.omega';source.write_text('parametro x=4;perda l=x*x;gradiente l em x;mostrar l;')
    result=evaluate(source,tmp_path/'candidates',lambda binary:binary.stat().st_size,levels=('-O0','-O2'))
    assert result['promoted'] is False and len(result['candidates'])==2
    assert all(row['admission']['valid'] for row in result['candidates'])
