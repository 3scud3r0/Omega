"""OM-057: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_coder.specifications import from_requirements

def test_requirements_become_reviewable_contracts_and_duplicates_are_rejected():
    contract={'id':'a','description':'sum equals 3','oracle':'sum_oracle','fixtures':('pair',)}
    spec=from_requirements('add', [contract])
    assert spec.acceptance[0].oracle=='sum_oracle' and spec.requirement=='add'
    with pytest.raises(ValueError):from_requirements('add',[contract,contract])
