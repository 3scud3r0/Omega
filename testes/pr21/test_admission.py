"""Adversarial fixtures are policy tests, never actual regression evidence."""
from hashlib import sha256
import json
from pathlib import Path
import pytest
from omega_self_evolve_v2 import ouroboros


def test_signed_receipt_cannot_substitute_another_cost_experiment(tmp_path,monkeypatch):
    root=tmp_path/'prepared';generation=root/'generation';(generation/'bootstrap').mkdir(parents=True)
    baseline=tmp_path/'baseline';baseline.write_bytes(b'baseline-fixture')
    candidate=generation/'bootstrap/stage3';candidate.write_bytes(b'candidate-fixture')
    proof=generation/'optimization.lean';proof.write_text('example : (1 : Nat)=1 := rfl\n')
    regression=tmp_path/'regression.xml';regression.write_text('<testsuites/>')
    evidence={name:ouroboros.digest(path) for name,path in (
        ('base_sha256',baseline),('candidate_sha256',candidate),('proof_sha256',proof),('regression_sha256',regression))}
    (root/'prepared.json').write_text(json.dumps({**evidence,'cost_before':7,'cost_after':5}))
    monkeypatch.setattr(ouroboros,'compiler',lambda:baseline)
    monkeypatch.setattr(ouroboros,'audit_generation',lambda _: {'compiler_relative':'bootstrap/stage3','objective':{'before':7,'after':5}})
    def no_activation(*a,**k):raise AssertionError('A mismatched cost reached activation')
    monkeypatch.setattr(ouroboros,'activate',no_activation)
    with pytest.raises(ValueError,match='measured cost mismatch'):
        ouroboros.promote(root,regression,{**evidence,'cost_before':1000,'cost_after':0},'0'*128,
                          verifier_key='1'*64,proposer_key='2'*64,selection_root=tmp_path/'selection')
