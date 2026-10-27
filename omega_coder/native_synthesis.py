"""Executable finite coding workflow: search, native build, isolation and replay.

Reserved observations are never mounted in the search worker. A failed reserved
case rejects the first candidate; it does not initiate tuning against that set.
The independent Lean kernel checks observed native computations, not universal
correctness of a program inferred from examples or refinement of arbitrary C.
"""
from pathlib import Path
from fractions import Fraction
import hashlib
import re
import stat
import sys
import tempfile

from omega_platform.budget import Budget
from omega_platform.manifest import artifact_record
from omega_platform.sandbox import run as isolated_run
from omega_security.encoding import canonical, decode
from .contract_synthesis import rational, variables_contract, observations, MAX_CONSTANTS

FORMAT = 'omega-native-synthesis-1'
MAX_BYTES = 1024 * 1024
MAX_CASES = 64
ARTIFACT_NAMES = frozenset({
    'problem.json', 'search.json', 'candidate.json', 'program.omega', 'program',
    'program.c', 'program.build.json', 'native-result.json',
    'native-result.lean', 'native-result.verification.json', 'report.json',
})
SEARCH_BUDGET = Budget(wall_seconds=30, cpu_seconds=20)


def _write(path, value):
    with path.open('xb') as stream:
        stream.write(canonical(value, max_bytes=16 * MAX_BYTES, max_nodes=500000))


def _read(path, limit=MAX_BYTES):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Regular synthesis artifact required; symlinks refused')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Synthesis artifact byte budget exceeded')
    return data


def _examples(variables, cases):
    if type(cases) is not list or any(type(c) is not dict or set(c) != {'inputs', 'output'} for c in cases):
        raise ValueError('Cases must have exactly inputs and output')
    return observations(variables, [(c['inputs'], c['output']) for c in cases])


def contract(data):
    fields = {'variables', 'constants', 'examples', 'validation_examples'}
    if type(data) is not dict or not fields - {'constants'} <= set(data) <= fields:
        raise ValueError('Variables, training examples and reserved validation examples required')
    variables = variables_contract(data['variables'])
    constants = data.get('constants', [0, 1])
    if type(constants) is not list or len(constants) > MAX_CONSTANTS:
        raise ValueError('Bounded constants required')
    constants = [str(rational(c)) for c in constants]
    if not variables and not constants:
        raise ValueError('An expression atom is required')
    train = _examples(variables, data['examples'])
    reserved = _examples(variables, data['validation_examples'])
    if len(train) + len(reserved) > MAX_CASES:
        raise ValueError('At most 64 total native observations allowed')
    keys = {tuple(env[v] for v in variables) for env, _ in train}
    if any(tuple(env[v] for v in variables) in keys for env, _ in reserved):
        raise ValueError('Training and validation inputs overlap')
    def pack(cases):
        return [{'inputs': {v: str(env[v]) for v in variables}, 'output': str(target)}
                for env, target in cases]
    return {'variables': list(variables), 'constants': constants,
            'examples': pack(train), 'validation_examples': pack(reserved)}


def _expression(expression, variables, *, max_nodes):
    remaining = max_nodes
    # Copy into an immutable bounded AST. No eval, templates or source snippets.
    def visit(expr):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or type(expr) not in (list, tuple) or not expr or type(expr[0]) is not str:
            raise ValueError('Expression tree budget/schema violation')
        op = expr[0]
        if op == 'var' and len(expr) == 2 and type(expr[1]) is str and expr[1] in variables:
            return (op, expr[1])
        if op == 'const' and len(expr) == 2:
            return (op, rational(expr[1]))
        if op in ('+', '-', '*') and len(expr) == 3:
            return (op, visit(expr[1]), visit(expr[2]))
        raise ValueError('Unsupported scalar expression')
    return visit(expression)


def _render(expression, names):
    if expression[0] == 'var':
        return names[expression[1]]
    if expression[0] == 'const':
        value = expression[1]
        return f'({value.numerator}/{value.denominator})'
    return f'({_render(expression[1], names)}{expression[0]}{_render(expression[2], names)})'


def source_for(expression, problem):
    lines = []
    for i, case in enumerate(problem['examples'] + problem['validation_examples']):
        names = {v: f'input_{i}_{j}' for j, v in enumerate(problem['variables'])}
        for variable, name in names.items():
            value = rational(case['inputs'][variable])
            lines.append(f'parametro {name}=({value.numerator}/{value.denominator});')
        lines.append(f'tensor result_{i}={_render(expression, names)};')
        lines.append(f'mostrar result_{i};')
    text = '\n'.join(lines) + '\n'
    if len(text.encode()) > 256 * 1024:
        raise ValueError('Generated native source byte budget exceeded')
    return text


def _search(problem, directory, max_nodes, max_candidates, budget):
    # Do not mount problem.json: it contains the reserved targets and inputs.
    public = {k: problem[k] for k in ('variables', 'constants', 'examples')}
    public.update(max_nodes=max_nodes, max_candidates=max_candidates)
    path = directory / 'search.json'
    _write(path, public)
    package = Path(__file__).resolve().parent
    worker = package / 'synthesis_worker.py'
    outcome = isolated_run(
        [sys.executable, '-E', '-S', '-B', worker, path],
        readonly=[worker, package / 'contract_synthesis.py', path, Path(sys.base_prefix) / 'lib'],
        budget=budget, check=True,
    )
    response = decode(outcome.stdout.encode())
    if type(response) is not dict or set(response) != {'format', 'candidate'} or response['format'] != 'omega-scalar-search-1':
        raise ValueError('Invalid isolated search response')
    candidate = response['candidate']
    if candidate is not None:
        if type(candidate) is not dict or set(candidate) != {'expression', 'checked', 'universal'}:
            raise ValueError('Invalid candidate schema')
        if candidate['universal'] is not False or type(candidate['checked']) is not int or not 1 <= candidate['checked'] <= max_candidates:
            raise ValueError('Invalid candidate claim/budget')
        _expression(candidate['expression'], problem['variables'], max_nodes=max_nodes)
    return candidate, {'sandboxed': outcome.sandboxed, 'budget': outcome.budget,
                       'wall_seconds': outcome.wall_seconds}


def run(problem, directory, *, max_nodes=7, max_candidates=10000,
        search_budget=SEARCH_BUDGET, execution_budget=Budget()):
    """Write to a fresh directory. Exceptions preserve partial evidence, never pass."""
    if type(max_nodes) is not int or not 1 <= max_nodes <= 31:
        raise ValueError('Invalid expression node budget')
    if type(max_candidates) is not int or not 1 <= max_candidates <= 100000:
        raise ValueError('Invalid candidate budget')
    if type(search_budget) is not Budget or type(execution_budget) is not Budget:
        raise ValueError('Explicit validated OS budgets required')
    problem = contract(problem)
    directory = Path(directory).absolute()
    directory.mkdir(parents=True, exist_ok=False)
    subject = hashlib.sha256(canonical(problem)).hexdigest()
    _write(directory / 'problem.json', problem)
    report = {'format': FORMAT, 'status': 'failed', 'problem_sha256': subject,
              'checks_passed': False, 'universal_proof': False, 'promoted': False,
              'claim': 'exact observations only; no universal or C refinement proof',
              'limits': {'max_nodes': max_nodes, 'max_candidates': max_candidates},
              'execution_budget': execution_budget.__dict__, 'cases': []}
    stage = 'search'
    try:
        candidate, telemetry = _search(problem, directory, max_nodes, max_candidates, search_budget)
        report['search_execution'] = telemetry
        report['candidate'] = candidate
        _write(directory / 'candidate.json', candidate)
        if candidate is None:
            report['status'] = 'exhausted'
        else:
            stage = 'build'
            expression = _expression(candidate['expression'], problem['variables'], max_nodes=max_nodes)
            source = directory / 'program.omega'
            with source.open('x', encoding='utf-8') as stream:
                stream.write(source_for(expression, problem))
            from omega_selfhost import driver
            driver.build_checked(source, directory / 'program').unwrap()
            stage = 'execute_and_verify'
            data, admission = driver.run(directory / 'program', destination=directory / 'native-result.json',
                                         budget=execution_budget)
            if admission.get('valid') is not True or admission.get('execution', {}).get('sandboxed') is not True:
                raise ValueError('Native independent admission/isolation missing')
            stage = 'observations'
            for group in ('examples', 'validation_examples'):
                offset = 0 if group == 'examples' else len(problem['examples'])
                for j, case in enumerate(problem[group]):
                    actual = data['values'][f'result_{offset+j}']
                    # The native protocol is canonical rational text. Its kernel
                    # has already checked these values against the actual IR.
                    passed = actual == case['output']
                    report['cases'].append({'split': 'train' if group == 'examples' else 'reserved',
                                            'index': j, 'expected': case['output'],
                                            'actual': actual, 'passed': passed})
            report['checks_passed'] = all(case['passed'] for case in report['cases'])
            report['status'] = 'checks_passed' if report['checks_passed'] else 'rejected'
    except Exception as exc:
        report.update(stage=stage, error_type=type(exc).__name__)
        raise
    finally:
        _write(directory / 'report.json', report)
        files = [p for p in directory.iterdir() if p.name in ARTIFACT_NAMES and p.is_file()]
        _write(directory / 'manifest.json', {'format': 'omega-synthesis-artifacts-1',
                                           'problem_sha256': subject,
                                           'files': artifact_record(files, directory)})
    return report


def _replay_budget(record, policy):
    if type(policy) is not Budget or type(record) is not dict:
        raise ValueError('Supervisor replay budget policy required')
    recorded = Budget(**record)
    if any(getattr(recorded, field) > value for field, value in policy.__dict__.items()):
        raise ValueError('Archived replay budget exceeds supervisor policy')
    return recorded


def audit(directory, *, expected_problem_sha256=None,
          search_policy=SEARCH_BUDGET, execution_policy=Budget()):
    """Rebuild and rerun independently. Integrity is not origin authentication.

    An external supervisor may bind this review to an expected problem digest.
    Never execute the archived binary: rebuild from the bounded regenerated AST.
    """
    directory = Path(directory).absolute()
    manifest = decode(_read(directory / 'manifest.json'))
    if type(manifest) is not dict or set(manifest) != {'format', 'problem_sha256', 'files'} or manifest['format'] != 'omega-synthesis-artifacts-1':
        raise ValueError('Invalid synthesis artifact manifest')
    files = manifest['files']
    required = {'problem.json', 'search.json', 'candidate.json', 'report.json'}
    if type(files) is not dict or not required <= set(files) <= ARTIFACT_NAMES:
        raise ValueError('Missing or unknown synthesis artifacts')
    for name, record in files.items():
        data = _read(directory / name, limit=64 * MAX_BYTES)
        if record != {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}:
            raise ValueError('Synthesis artifact integrity mismatch: ' + name)
    problem = contract(decode(_read(directory / 'problem.json')))
    subject = hashlib.sha256(canonical(problem)).hexdigest()
    if manifest['problem_sha256'] != subject:
        raise ValueError('Problem/manifest subject mismatch')
    if expected_problem_sha256 is not None:
        if type(expected_problem_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', expected_problem_sha256) or expected_problem_sha256 != subject:
            raise ValueError('Artifact does not match the authorized problem')
    previous = decode(_read(directory / 'report.json'))
    if type(previous) is not dict or previous.get('format') != FORMAT or previous.get('problem_sha256') != subject:
        raise ValueError('Invalid synthesis report/subject')
    if previous.get('candidate') is not None:
        native_files = {'program.omega', 'program', 'program.c', 'program.build.json',
                        'native-result.json', 'native-result.verification.json'}
        if not native_files <= set(files):
            raise ValueError('Incomplete native synthesis artifact set')
    if previous.get('search_execution', {}).get('sandboxed') is not True:
        raise ValueError('Archived search isolation evidence missing')
    limits = previous['limits']
    if type(limits) is not dict or set(limits) != {'max_nodes', 'max_candidates'}:
        raise ValueError('Invalid synthesis replay limits')
    search_budget = _replay_budget(previous['search_execution']['budget'], search_policy)
    execution_budget = _replay_budget(previous['execution_budget'], execution_policy)
    with tempfile.TemporaryDirectory(prefix='omega-synthesis-audit-') as tmp:
        rebuilt = Path(tmp) / 'replay'
        current = run(problem, rebuilt, **limits, search_budget=search_budget, execution_budget=execution_budget)
        for name in ('problem.json', 'search.json', 'candidate.json', 'program.omega', 'native-result.json'):
            if (rebuilt / name).exists():
                if name not in files or _read(directory / name, 64 * MAX_BYTES) != _read(rebuilt / name, 64 * MAX_BYTES):
                    raise ValueError('Independent synthesis replay disagreement: ' + name)
        for key in ('status', 'checks_passed', 'candidate', 'cases', 'universal_proof', 'promoted'):
            if previous.get(key) != current.get(key):
                raise ValueError('Independent report replay disagreement: ' + key)
    return {'format': 'omega-native-synthesis-audit-1', 'matches_archived': True,
            'checks_passed': current['checks_passed'], 'status': current['status'],
            'problem_sha256': subject, 'problem_bound': expected_problem_sha256 is not None,
            'origin_authenticated': False, 'universal_proof': False, 'promoted': False}
