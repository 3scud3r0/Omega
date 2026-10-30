"""Independent Lean checking and actual native-to-paper experiment evidence."""
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import pytest
from omega_science.runtime import run,prove,inspect_lean_transcript
from omega_science.experiment import execute
from omega_native.codec import decode
from omega_platform.sandbox import ExecutionFailure


def test_numeric_dispatch_preserves_operands_and_independent_lean_accepts(tmp_path):
    request={'witnesses':[{'left':[Q(1,2),Q(1,2)],'right':[1]},
                          {'left_dot':[[2,3],[4,5]],'right':[23]},
                          {'left_squares':[Q(3,5),Q(4,5)],'right':[1]},
                          {'nonnegative':Q(7,9)}]}
    job=run(104,request)
    assert '((1 : Rat) / 2)' in job['value']
    receipt=prove(request,tmp_path/'proof')
    assert receipt['verified'] and len(receipt['theorems'])==4
    assert not receipt['scientific_model_accepted'] and not receipt['origin_authenticated']
    assert receipt['source_sha256']==hashlib.sha256((tmp_path/'proof/Observation.lean').read_bytes()).hexdigest()
    assert (tmp_path/'proof/Observation.olean').is_file()


@pytest.mark.parametrize('witness',[{'left':[2],'right':[3]},{'nonnegative':-1}])
def test_false_scientific_numeric_obligation_is_rejected_without_receipt(tmp_path,witness):
    with pytest.raises(ValueError,match='Lean rejected'):
        prove({'witnesses':[witness]},tmp_path/'rejected')
    assert not (tmp_path/'rejected/receipt.json').exists()
    assert (tmp_path/'rejected/lean.log').is_file()


@pytest.mark.parametrize('witness',[
    {'left':[1],'left_squares':[1],'right':[1]},
    {'left_dot':[[1],[1,2]],'right':[1]},
    {'nonnegative':1,'left':[1]},
    {'left':['1; #eval IO.println "injected"'],'right':[1]},
    {'left':[1],'right':[1],'proof':'by trivial'},
])
def test_untrusted_papers_cannot_inject_tactics_or_ambiguous_statements(witness):
    with pytest.raises(ExecutionFailure):run(104,{'witnesses':[witness]})


@pytest.mark.parametrize('output,expected',[
    ("'x' depends on axioms: [sorryAx]",['x']),
    ("'x' depends on axioms: [propext]",['missing']),
    ("'x' depends on axioms: []\n'y' depends on axioms: []",['x']),
    ("'x' depends on axioms: [propext]\n'x' does not depend on any axioms",['x']),
])
def test_axiom_audit_fails_closed_for_missing_extra_or_admitted_theorems(output,expected):
    with pytest.raises(ValueError):inspect_lean_transcript(output,expected)


def test_native_stoichiometry_experiment_builds_real_executable_and_checks_each_conserved_row(tmp_path):
    request={'conservation_matrix':[[2,0,-2],[0,2,-1]]}
    directory=tmp_path/'water'
    receipt=execute(23,request,directory)
    assert receipt['numeric_obligations_verified']
    assert not receipt['scientific_model_accepted'] and not receipt['external_publication']
    observed=decode((directory/'observation.json').read_text())
    assert observed['value']==[2,1,2]
    paper=decode((directory/'paper.json').read_text())
    assert bytes.fromhex(paper['artifacts']['program.hex']).startswith(b'\x7fELF')
    assert 'runtime.h' in paper['artifacts']['program.c']
    assert '2 : Rat' in paper['artifacts']['Proof.lean']
    assert ' * ' in paper['artifacts']['Proof.lean']
    for name,digest in receipt['files'].items():
        assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
    assert (directory/'runtime-headers.json').exists()
    with pytest.raises(FileExistsError):execute(23,request,directory)


def test_experiment_refuses_a_kernel_without_an_independent_contract(tmp_path):
    with pytest.raises(ValueError,match='contract'):
        execute(99,{},tmp_path/'not-authorized')
    assert not (tmp_path/'not-authorized').exists()


def test_receipt_is_bound_to_checked_snapshot_when_caller_mutates_original(tmp_path,monkeypatch):
    from copy import deepcopy
    from omega_science import runtime
    from omega_security.encoding import canonical
    request={'witnesses':[{'left':[1],'right':[1]}]}
    checked_input=deepcopy(request)
    original_run=runtime.run
    def concurrent_update(identifier,payload,**options):
        result=original_run(identifier,payload,**options)
        request['witnesses'][0]['right']=[2]
        return result
    monkeypatch.setattr(runtime,'run',concurrent_update)
    receipt=runtime.prove(request,tmp_path/'proof')
    assert receipt['verified']
    assert request!=checked_input
    assert receipt['request_sha256']==hashlib.sha256(canonical(checked_input)).hexdigest()
    assert receipt['request_sha256']!=hashlib.sha256(canonical(request)).hexdigest()
