from pathlib import Path

from omega_platform.budget import PROOF_BUDGET
from omega_platform.sandbox import trusted
from omega_selfhost.proof import lake_binary

ROOT=Path(__file__).resolve().parents[2]


def test_formal_operational_examples():
    result=trusted([lake_binary(),'env','lean',ROOT/'testes/lean/OperationalExamples.lean'],
                   cwd=ROOT/'formal/tensor',budget=PROOF_BUDGET)
    assert result.ok,result.stdout+result.stderr
    assert 'sorryAx' not in result.stdout+result.stderr
