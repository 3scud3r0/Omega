import copy
import json
from pathlib import Path
import pytest
from omega_self_mutate.rules import discover_rule,validate_rule
from omega_self_mutate.bootstrap import evolve
from omega_self_mutate.activation import activate,load_active,audit_generation,deactivate


@pytest.fixture(scope='module')
def generation(tmp_path_factory):
    root=tmp_path_factory.mktemp('mutation')/'generation'
    rule=discover_rule('(x*2)-x',iterations=128)
    result=evolve(rule,root)
    return root,result


def test_four_native_stages_full_equivalence_and_activation(generation,tmp_path):
    root,result=generation
    assert result['bootstrap']['fixed_point'] and len(result['bootstrap']['stages'])==4
    assert result['objective']['after']<result['objective']['before']
    assert 'domain_' in (root/'optimization.lean').read_text()
    selected=activate(root,selection_root=tmp_path)
    assert load_active(selection_root=tmp_path)==Path(selected['binary'])
    deactivate(selection_root=tmp_path)
    assert load_active(selection_root=tmp_path) is None


@pytest.mark.parametrize('lhs,rhs',[('x+1','x'),('x/x','x'),('x*0','x')])
def test_nonidentical_or_partial_rules_rejected(lhs,rhs):
    with pytest.raises(ValueError):validate_rule(lhs,rhs)


def test_forged_generation_cannot_authenticate_its_own_executable(generation,tmp_path):
    import shutil,hashlib
    source,_=generation;root=tmp_path/'forged';shutil.copytree(source,root)
    binary=root/'bootstrap/stage3';binary.write_bytes(b'forged executable')
    path=root/'generation.json';record=json.loads(path.read_text())
    record['files']['bootstrap/stage3']=hashlib.sha256(binary.read_bytes()).hexdigest()
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='Untrusted'):audit_generation(root)
    assert not (tmp_path/'active.json').exists()


def test_certificate_v2_is_not_a_data_only_validity_receipt(generation,tmp_path):
    from omega_platform.sandbox import trusted
    from omega_selfhost.driver import ROOT
    root,_=generation
    witness=root/'probe.c.opt.json'
    from omega_platform.budget import PROOF_BUDGET
    result=trusted([ROOT/'formal/tensor/.lake/build/bin/omega_tensor_kernel',witness],budget=PROOF_BUDGET,check=False)
    assert result.returncode!=0


def test_activation_does_not_read_fifos_or_symlinked_manifests(tmp_path):
    import os
    root=tmp_path/'fifo';root.mkdir();os.mkfifo(root/'generation.json')
    with pytest.raises(ValueError,match='regular'):audit_generation(root)
    other=tmp_path/'symlink';other.mkdir();(other/'generation.json').symlink_to(root/'generation.json')
    with pytest.raises(ValueError,match='regular'):audit_generation(other)
