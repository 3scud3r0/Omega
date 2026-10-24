from pathlib import Path
from unittest.mock import patch
import json,shutil,signal,tempfile
import pytest
from omega_platform.corpus import Case,evaluate,load,CorpusError
from omega_platform.sandbox import Outcome,ExecutionFailure,IsolationUnavailable

ROOT=Path(__file__).resolve().parents[2]


def test_manifest_classifies_every_program_including_procedural():
    cases=load(ROOT/'testes/corpus.json',ROOT)
    assert len(cases)==len(list((ROOT/'exemplos').rglob('*.omega')))
    assert any(c.language=='procedural' and c.expected=='accept' for c in cases)
    assert sum(c.expected!='accept' for c in cases)==4


def test_new_or_missing_examples_are_count_errors_not_success():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);shutil.copytree(ROOT/'exemplos',root/'exemplos')
        (root/'exemplos/new.omega').write_text('mostrar x;')
        with pytest.raises(CorpusError,match='coverage mismatch'):
            load(ROOT/'testes/corpus.json',root)


def test_expected_rejection_does_not_hide_missing_sandbox_or_signal():
    case=Case('exemplos/erro_de_tipo.omega','tensor','compile_reject','rejection','Parametro inexistente')
    with patch('omega_selfhost.driver.build',side_effect=IsolationUnavailable('missing tool')):
        assert evaluate(case,ROOT).status=='infrastructure'
    outcome=Outcome(('compiler',),-signal.SIGSEGV,'','Parametro inexistente',0.01,False,True,{})
    with patch('omega_selfhost.driver.build',side_effect=ExecutionFailure(outcome)):
        assert evaluate(case,ROOT).status=='failed'
    outcome=Outcome(('compiler',),1,'','Omega: Parametro inexistente',0.01,False,True,{})
    with patch('omega_selfhost.driver.build',side_effect=ExecutionFailure(outcome)):
        assert evaluate(case,ROOT).status=='expected_rejection'
