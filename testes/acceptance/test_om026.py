"""OM-026: executable checks; source delivery, not a recorded pass."""
import pytest
pytestmark=pytest.mark.lean

def test_formal_obligations_compile_without_admissions(lean_case):
    lean_case(26)
