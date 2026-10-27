"""Real synthesis/build/kernel/replay tests, plus adversarial data boundaries."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import pytest

from omega_coder import contract_synthesis as synthesis
from omega_coder import native_synthesis as workflow
from omega_security.encoding import canonical

ROOT = Path(__file__).resolve().parents[2]


def problem():
    return json.loads((ROOT / 'exemplos/sintese_racional.json').read_text())


@pytest.fixture(scope='module')
def native_bundle(tmp_path_factory):
    directory = tmp_path_factory.mktemp('native-synthesis') / 'result'
    result = workflow.run(problem(), directory, max_nodes=3, max_candidates=100)
    return directory, result


def test_actual_source_build_isolated_execution_and_lean_admission(native_bundle):
    directory, result = native_bundle
    assert result['status'] == 'checks_passed' and result['checks_passed'] is True
    assert len(result['cases']) == 4 and all(c['passed'] for c in result['cases'])
    assert result['universal_proof'] is False and result['promoted'] is False
    assert result['search_execution']['sandboxed'] is True
    search = json.loads((directory / 'search.json').read_text())
    assert set(search) == {'variables', 'constants', 'examples', 'max_nodes', 'max_candidates'}
    assert 'validation_examples' not in search and '-3/2' not in (directory / 'search.json').read_text()
    admission = json.loads((directory / 'native-result.verification.json').read_text())
    assert admission['valid'] is True and admission['execution']['sandboxed'] is True
    build = json.loads((directory / 'program.build.json').read_text())
    assert build['native_c_flags'] == ['-std=gnu11', '-O2', '-s', '-lgmp']
    assert (directory / 'program.c').is_file() and (directory / 'program').is_file()


def test_replay_rebuilds_and_binds_authorized_problem(native_bundle):
    directory, result = native_bundle
    replay = workflow.audit(directory, expected_problem_sha256=result['problem_sha256'])
    assert replay['checks_passed'] and replay['matches_archived'] and replay['problem_bound']
    assert not replay['origin_authenticated'] and not replay['universal_proof']
    with pytest.raises(ValueError, match='authorized problem'):
        workflow.audit(directory, expected_problem_sha256='0' * 64)


def test_replay_refuses_tampered_source_and_report(native_bundle, tmp_path):
    import shutil
    directory, _ = native_bundle
    copy = tmp_path / 'copy'
    shutil.copytree(directory, copy)
    (copy / 'program.omega').write_text('malicious source')
    with pytest.raises(ValueError, match='integrity'):
        workflow.audit(copy)
    (copy / 'program.omega').write_bytes((directory / 'program.omega').read_bytes())
    report = json.loads((copy / 'report.json').read_text())
    report['universal_proof'] = True
    (copy / 'report.json').write_bytes(canonical(report))
    manifest = json.loads((copy / 'manifest.json').read_text())
    data = (copy / 'report.json').read_bytes()
    manifest['files']['report.json'] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    (copy / 'manifest.json').write_bytes(canonical(manifest))
    with pytest.raises(ValueError, match='report replay disagreement'):
        workflow.audit(copy)


def test_reserved_failure_rejects_without_tuning(tmp_path):
    data = problem()
    data['examples'] = [{'inputs': {'x': 0}, 'output': 0}]
    data['validation_examples'] = [{'inputs': {'x': 1}, 'output': 2}]
    report = workflow.run(data, tmp_path / 'reject', max_nodes=3, max_candidates=100)
    assert report['candidate']['expression'] == ['var', 'x']  # First training fit, not 2*x.
    assert report['candidate']['checked'] == 1
    assert report['status'] == 'rejected' and not report['checks_passed']
    assert report['cases'][0]['passed'] and not report['cases'][1]['passed']
    replay = workflow.audit(tmp_path / 'reject')
    assert replay['matches_archived'] and not replay['checks_passed']


def test_exhausted_search_is_not_pass_or_execution(tmp_path):
    report = workflow.run(problem(), tmp_path / 'exhausted', max_nodes=1, max_candidates=1)
    assert report['status'] == 'exhausted' and not report['checks_passed']
    assert report['candidate'] is None and not (tmp_path / 'exhausted' / 'program').exists()
    assert workflow.audit(tmp_path / 'exhausted')['status'] == 'exhausted'


def test_existing_destination_is_preserved(native_bundle):
    directory, _ = native_bundle
    before = (directory / 'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        workflow.run(problem(), directory)
    assert (directory / 'manifest.json').read_bytes() == before


@pytest.mark.parametrize('mutation', ['overlap', 'duplicate', 'unknown', 'missing', 'float', 'name', 'too_many'])
def test_contract_rejects_invalid_and_contaminated_inputs(mutation):
    data = problem()
    if mutation == 'overlap':
        data['validation_examples'][0]['inputs']['x'] = '2/2'
    elif mutation == 'duplicate':
        data['examples'].append(deepcopy(data['examples'][0]))
    elif mutation == 'unknown':
        data['universal_proof'] = True
    elif mutation == 'missing':
        del data['examples'][0]['inputs']['x']
    elif mutation == 'float':
        data['examples'][0]['output'] = 2.0
    elif mutation == 'name':
        data['variables'] = ['x; print(secret)']
    else:
        data['validation_examples'] = [{'inputs': {'x': i + 10}, 'output': i + 11} for i in range(64)]
    with pytest.raises(ValueError):
        workflow.contract(data)


@pytest.mark.parametrize('value', [True, 1.25, '1e2', '1/0', 2 ** 257, Fraction(1, 2 ** 257)])
def test_rational_boundaries(value):
    with pytest.raises(ValueError):
        synthesis.rational(value)


@pytest.mark.parametrize('kwargs', [{'max_nodes': True}, {'max_candidates': 0}, {'max_candidates': 100001}, {'max_nodes': 32}])
def test_search_resource_arguments_are_checked(kwargs):
    with pytest.raises(ValueError):
        synthesis.synthesize(['x'], [0], [({'x': 1}, 2)], **kwargs)


def test_streaming_enumeration_stops_at_global_candidate_budget(monkeypatch):
    count = 0
    original = synthesis.product
    def counted(*args):
        nonlocal count
        for item in original(*args):
            count += 1
            yield item
    monkeypatch.setattr(synthesis, 'product', counted)
    assert synthesis.synthesize(['x'], [0, 1, 2, 3, 4, 5], [({'x': 1}, 999)],
                                max_nodes=31, max_candidates=10) is None
    # Seven atoms, three compound evaluations, at most one lookahead.
    assert count <= 4


def test_closed_ast_and_capture_free_emission():
    data = workflow.contract(problem())
    expr = workflow._expression(['+', ['var', 'x'], ['const', '1/2']], ['x'], max_nodes=3)
    source = workflow.source_for(expr, data)
    assert 'input_0_0' in source and 'input_3_0' in source
    assert 'result_3' in source and '(1/2)' in source
    for invalid in (['eval', 'secret'], ['var', 'secret'], ['+', ['const', 1]], ['const', False]):
        with pytest.raises(ValueError):
            workflow._expression(invalid, ['x'], max_nodes=31)


def test_cli_json_boundary_and_native_exit_status(native_bundle, tmp_path, capsys):
    from omega_agent.cli import main
    duplicate = tmp_path / 'duplicate.json'
    duplicate.write_text('{"variables": [], "variables": ["x"]}')
    assert main(['synthesize', str(duplicate)]) == 1
    assert json.loads(capsys.readouterr().err)['ok'] is False
    assert main(['synthesize-native', str(ROOT / 'exemplos/sintese_racional.json')]) == 1
    capsys.readouterr()
    assert main(['synthesize-native', str(ROOT / 'exemplos/sintese_racional.json'),
                 '--saida', str(tmp_path / 'cli'), '--max-size', '1', '--max-candidates', '1']) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc['ok'] is True and doc['value']['status'] == 'exhausted'


def test_replay_refuses_missing_native_artifact_and_symlink(native_bundle, tmp_path):
    import shutil
    directory, _ = native_bundle
    copy = tmp_path / 'copy'
    shutil.copytree(directory, copy)
    manifest = json.loads((copy / 'manifest.json').read_text())
    del manifest['files']['program']
    (copy / 'manifest.json').write_bytes(canonical(manifest))
    with pytest.raises(ValueError, match='Incomplete native'):
        workflow.audit(copy)
    shutil.copyfile(directory / 'manifest.json', copy / 'manifest.json')
    (copy / 'program').unlink()
    (copy / 'program').symlink_to(directory / 'program')
    with pytest.raises(ValueError, match='symlinks refused'):
        workflow.audit(copy)


def test_interrupted_native_build_preserves_failure_not_success(tmp_path, monkeypatch):
    from omega_selfhost import driver
    def fail(*args, **kwargs):
        raise RuntimeError('deliberate toolchain failure')
    monkeypatch.setattr(driver, 'build_checked', fail)
    directory = tmp_path / 'failure'
    with pytest.raises(RuntimeError, match='deliberate toolchain failure'):
        workflow.run(problem(), directory, max_nodes=3, max_candidates=100)
    report = json.loads((directory / 'report.json').read_text())
    assert report['status'] == 'failed' and report['checks_passed'] is False
    assert report['stage'] == 'build' and report['error_type'] == 'RuntimeError'
    assert (directory / 'manifest.json').exists()


def test_non_default_c_optimization_flag_is_preserved_in_provenance(tmp_path):
    from omega_selfhost import driver
    source = tmp_path / 'simple.omega'
    source.write_text('parametro x=2;tensor y=x+1;mostrar y;')
    driver.build(source, tmp_path / 'binary', optimization='-O0')
    record = json.loads((tmp_path / 'binary.build.json').read_text())
    assert record['native_c_flags'][1] == '-O0'


@pytest.mark.parametrize('budget', ['search_execution', 'execution_budget'])
def test_untrusted_archive_cannot_raise_supervisor_resource_policy(native_bundle, tmp_path, budget):
    import shutil
    directory, _ = native_bundle
    copy = tmp_path / 'copy'
    shutil.copytree(directory, copy)
    report = json.loads((copy / 'report.json').read_text())
    limits = report['search_execution']['budget'] if budget == 'search_execution' else report['execution_budget']
    limits['memory_bytes'] *= 2
    data = canonical(report)
    (copy / 'report.json').write_bytes(data)
    manifest = json.loads((copy / 'manifest.json').read_text())
    manifest['files']['report.json'] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    (copy / 'manifest.json').write_bytes(canonical(manifest))
    with pytest.raises(ValueError, match='exceeds supervisor policy'):
        workflow.audit(copy)


def test_global_build_provenance_covers_new_subsystems():
    from omega_platform.manifest import build_manifest
    record = build_manifest(ROOT, [ROOT / 'omega_coder/native_synthesis.py'])
    for path in ('omega_agent/runtime.py', 'omega_coder/native_synthesis.py',
                 'omega_coder/synthesis_worker.py', 'omega_security/capabilities.py',
                 'omega_memory/privacy.py', 'omega_evolution/promotion.py',
                 'omega_tools/capability_adapter.py', 'omega_learning/active_learning.py',
                 'omega_bench/reproduction.py', 'omega_open/engine.py'):
        assert record['sources'][path] == hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
