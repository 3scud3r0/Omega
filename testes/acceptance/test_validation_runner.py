"""Contracts for the future runner; these tests have not been executed."""
import importlib.util
import json
from pathlib import Path
import pytest


@pytest.fixture
def runner():
    path=Path(__file__).resolve().parents[2]/'scripts/validate-roadmap.py'
    spec=importlib.util.spec_from_file_location('omega_validation_runner',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_default_cli_only_describes_plans(runner,monkeypatch,capsys):
    def forbidden(*args,**kwargs):raise AssertionError('Planning started execution')
    monkeypatch.setattr(runner,'execute_plan',forbidden)
    assert runner.main(['--task','OM-018'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['execution'] is False and result['plans'][0]['status']=='not_run'


def test_plan_cannot_insert_unreviewed_host_command(runner,tmp_path,monkeypatch):
    original=runner.load_plan('OM-019');original['steps'][0]['argv']=['{python}','-c','print("arbitrary host execution")']
    folder=tmp_path/'validation/plans';folder.mkdir(parents=True)
    (folder/'om019.json').write_text(json.dumps(original))
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    with pytest.raises(ValueError):runner.load_plan('OM-019')


def test_junit_counts_keep_skips_failures_and_zero_cases_pending(runner,tmp_path):
    path=tmp_path/'junit.xml'
    path.write_text('<testsuites><testsuite><testcase name="a"/><testcase name="b"><skipped/></testcase><testcase name="c"><failure/></testcase></testsuite></testsuites>')
    assert runner.junit_counts(path)=={'cases':3,'failures':1,'errors':0,'skipped':1,'passed':1}
    path.write_text('<testsuites/>')
    with pytest.raises(ValueError):runner.junit_counts(path)


def test_path_escape_is_not_a_validation_input(runner):
    with pytest.raises(ValueError):runner.relative_file('../outside.py')
    with pytest.raises(ValueError):runner.relative_file('/etc/passwd')
