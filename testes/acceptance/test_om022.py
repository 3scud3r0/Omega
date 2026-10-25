"""OM-022: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_selfhost.wasm_backend import run,compile_ir
from omega_platform.wasm import execute
from omega_platform.sandbox import ExecutionFailure

def test_scalar_wasm_matches_integer_reference(typed_graph):
    result=run(typed_graph,'l',{'x':7})
    assert result['value']==49 and result['fuel_remaining']>=0

def test_wasm_rejects_imports_and_traps_overflow(typed_graph):
    with pytest.raises(ExecutionFailure):execute('(module (import "env" "x" (func)))')
    with pytest.raises(ExecutionFailure):run(typed_graph,'l',{'x':2**62})
    with pytest.raises(ValueError):execute('(module)',(True,))
