"""OM-103: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_evolution.isolated_patches import IsolatedPatch
from omega_evolution.component_registry import Component,ComponentRegistry

def test_patch_applies_only_inside_authorized_worktree(tmp_path,signed_authority):
    verifier,mint=signed_authority;root=tmp_path/'candidate';root.mkdir();(root/'planner').mkdir()
    class Tree:
        path=root
        def diff(self):return 'reviewable diff'
    registry=ComponentRegistry([Component('planner',('planner',),True,('tests',))])
    patch=IsolatedPatch(Tree(),registry,'planner',verifier,'agent',mint(['code.write'],root=root))
    assert patch.apply({'planner/search.py':'value=1\n'})=='reviewable diff'
    assert (root/'planner/search.py').read_text()=='value=1\n'
    with pytest.raises(PermissionError):patch.apply({'../stable.py':'bad'})
    assert not (tmp_path/'stable.py').exists()
