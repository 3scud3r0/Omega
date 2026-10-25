"""OM-101: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_evolution.component_registry import Component,ComponentRegistry

def test_protected_scope_cannot_be_granted_by_overlapping_mutable_component():
    with pytest.raises(ValueError):ComponentRegistry([Component('all',('core',),True,('tests',)),Component('guard',('core/guard',),False,('review',))])
    registry=ComponentRegistry([Component('planner',('planner',),True,('tests',))])
    assert registry.require_patch('planner',['planner/search.py'])==('tests',)
    with pytest.raises(PermissionError):registry.require_patch('planner',['planner/../guard.py'])
