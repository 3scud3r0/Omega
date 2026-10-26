#!/usr/bin/env python3
"""Plan or explicitly execute roadmap checks; never equate tests with acceptance.

Default: print selected plans. Execution requires --execute. Candidates launched
by a test must still use the application sandbox. This runner executes reviewed
pytest sources as trusted host code and never installs dependencies or promotes
versions. Durable reports are written only under artifacts/validation/.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    'unit': {'wall_seconds': 300, 'cpu_seconds': 300, 'memory_bytes': 4 * 1024**3},
    'isolation': {'wall_seconds': 900, 'cpu_seconds': 900, 'memory_bytes': 8 * 1024**3},
    'native': {'wall_seconds': 1800, 'cpu_seconds': 1800, 'memory_bytes': 8 * 1024**3},
    'formal': {'wall_seconds': 1800, 'cpu_seconds': 1800, 'memory_bytes': 8 * 1024**3},
    'neural': {'wall_seconds': 900, 'cpu_seconds': 900, 'memory_bytes': 8 * 1024**3},
    'packaging': {'wall_seconds': 900, 'cpu_seconds': 900, 'memory_bytes': 8 * 1024**3},
    'sanitizer': {'wall_seconds': 900, 'cpu_seconds': 900, 'memory_bytes': 8 * 1024**3},
}


def relative_file(value):
    if type(value) is not str or not 0 < len(value) <= 4096 or '\\' in value or ':' in value or '\0' in value:
        raise ValueError('Invalid validation path')
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or str(path) != value or any(p in {'.', '..', '.git'} for p in path.parts):
        raise ValueError('Validation paths must remain in the checkout')
    target = ROOT / value
    if not target.resolve().is_relative_to(ROOT):
        raise ValueError('Validation path escapes through a symlink')
    return target


def load_plan(task):
    if type(task) is not str or not re.fullmatch(r'OM-\d{3}', task) or not 1 <= int(task[3:]) <= 150:
        raise ValueError('Select OM-001 through OM-150')
    path = ROOT / 'validation/plans' / (task.lower().replace('-', '') + '.json')
    raw = path.read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError('Validation plan byte limit exceeded')
    plan = json.loads(raw)
    fields = {'format', 'task', 'phase', 'acceptance', 'sources', 'test_files', 'steps', 'additional_obligations', 'independent_review_required', 'status'}
    if type(plan) is not dict or set(plan) != fields or plan['format'] != 'omega-validation-plan-1' or plan['task'] != task:
        raise ValueError('Unknown validation plan')
    for name in ('sources', 'test_files'):
        if type(plan[name]) is not list or not plan[name] or len(plan[name]) > 256:
            raise ValueError('Explicit bounded file inventory required')
        if len(set(plan[name])) != len(plan[name]):
            raise ValueError('Duplicate validation file')
        for value in plan[name]:
            relative_file(value)
    python_tests = [name for name in plan['test_files'] if name.endswith('.py')]
    if not python_tests or any(not name.startswith('testes/') for name in python_tests):
        raise ValueError('Reviewed pytest files under testes/ required')
    expected = ['{python}', '-m', 'pytest', '-q', *python_tests, '--junitxml', '{junit}']
    if type(plan['steps']) is not list or len(plan['steps']) != 1:
        raise ValueError('One reviewed pytest step per plan required')
    step = plan['steps'][0]
    if type(step) is not dict or set(step) != {'id', 'kind', 'argv', 'cwd', 'resource_profile'}:
        raise ValueError('Unknown validation step')
    if step['id'] != 'pytest' or step['kind'] != 'pytest' or step['argv'] != expected or step['cwd'] != '.' or step['resource_profile'] not in PROFILES:
        raise ValueError('Validation plans cannot introduce arbitrary host commands')
    if plan['independent_review_required'] is not True or plan['status'] != 'not_run':
        raise ValueError('A plan cannot predeclare successful validation')
    if type(plan['additional_obligations']) is not list or any(type(item) is not str for item in plan['additional_obligations']):
        raise ValueError('Explicit remaining acceptance obligations required')
    return plan


def source_snapshot(plan):
    paths = set(plan['sources'] + plan['test_files'])
    paths.update(('testes/acceptance/conftest.py', 'scripts/validate-roadmap.py', 'pyproject.toml'))
    paths.add('validation/plans/' + plan['task'].lower().replace('-', '') + '.json')
    result = {}
    for name in sorted(paths):
        path = relative_file(name)
        if not path.is_file():
            raise FileNotFoundError('Missing validation input: ' + name)
        size = path.stat().st_size
        if size > 32 * 1024**2:
            raise ValueError('Validation source byte budget exceeded')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def junit_counts(path):
    if not path.is_file() or path.stat().st_size > 32 * 1024**2:
        raise ValueError('Missing or oversized JUnit report')
    raw = path.read_bytes()
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('External entities are forbidden in reports')
    document = ET.fromstring(raw)
    cases = list(document.iter('testcase'))
    if not cases:
        raise ValueError('No test cases were executed')
    failures = sum(case.find('failure') is not None for case in cases)
    errors = sum(case.find('error') is not None for case in cases)
    skipped = sum(case.find('skipped') is not None for case in cases)
    return {'cases': len(cases), 'failures': failures, 'errors': errors, 'skipped': skipped,
            'passed': len(cases) - failures - errors - skipped}


def save_json(path, value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode('utf-8') + b'\n'
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def execute_plan(plan, run_directory):
    # Imports happen only after --execute, never while listing plans.
    from omega_platform.budget import Budget
    from omega_platform.sandbox import trusted
    from omega_security.secrets import redact
    task_directory = run_directory / plan['task'].lower().replace('-', '')
    task_directory.mkdir(mode=0o700)
    report = {'format': 'omega-validation-report-1', 'task': plan['task'],
              'status': 'infrastructure_error', 'acceptance_passed': None,
              'independent_review': None, 'additional_obligations': plan['additional_obligations'],
              'source_hashes': None, 'step': None, 'failure': None}
    started = time.monotonic()
    try:
        before = source_snapshot(plan)
        report['source_hashes'] = before
        step = plan['steps'][0]
        junit = task_directory / 'pytest.xml'
        argv = [sys.executable if item == '{python}' else str(junit) if item == '{junit}' else item for item in step['argv']]
        budget = Budget(**PROFILES[step['resource_profile']], output_bytes=8*1024**2,
                        processes=1024, open_files=4096, file_bytes=1024**3)
        outcome = trusted(argv, cwd=ROOT, budget=budget,
                          instrumented_children=step['resource_profile']=='sanitizer')
        stdout = redact(outcome.stdout).encode('utf-8')
        stderr = redact(outcome.stderr).encode('utf-8')
        (task_directory / 'stdout.log').write_bytes(stdout)
        (task_directory / 'stderr.log').write_bytes(stderr)
        report['step'] = {'argv': argv, 'returncode': outcome.returncode,
                          'termination': outcome.termination, 'wall_seconds': outcome.wall_seconds,
                          'resource_profile': step['resource_profile'], 'counts': None,
                          'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
                          'stderr_sha256': hashlib.sha256(stderr).hexdigest()}
        if source_snapshot(plan) != before:
            raise ValueError('Source inputs changed during validation')
        if outcome.termination != 'exit':
            report['status'] = 'budget_exceeded'
        elif outcome.returncode not in (0, 1):
            report['status'] = 'infrastructure_error'
        else:
            counts = junit_counts(junit)
            report['step']['counts'] = counts
            if outcome.returncode or counts['failures'] or counts['errors']:
                report['status'] = 'failed'
            elif counts['skipped']:
                report['status'] = 'incomplete'
            else:
                report['status'] = 'checks_passed_acceptance_pending'
    except Exception as exc:
        report['failure'] = {'type': type(exc).__name__, 'message': redact(str(exc))}
    finally:
        report['elapsed_seconds'] = time.monotonic() - started
        save_json(task_directory / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--all', action='store_true')
    selection.add_argument('--task', action='append', dest='tasks')
    parser.add_argument('--execute', action='store_true', help='explicitly run the reviewed checks')
    args = parser.parse_args(argv)
    tasks = [f'OM-{n:03d}' for n in range(1,151)] if args.all else sorted(set(args.tasks))
    plans = [load_plan(task) for task in tasks]
    if not args.execute:
        print(json.dumps({'execution': False, 'plans': plans}, ensure_ascii=False, indent=2))
        return 0
    base = ROOT / 'artifacts/validation'
    if not base.resolve().is_relative_to(ROOT):
        raise ValueError('Validation output escaped the checkout')
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12]
    directory = base / run_id
    directory.mkdir(mode=0o700)
    sys.path.insert(0,str(ROOT))
    commit = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    dirty = bool(subprocess.run(['git','status','--porcelain'],cwd=ROOT,check=True,capture_output=True,text=True).stdout)
    save_json(directory/'run.json', {'format':'omega-validation-run-1','id':run_id,'commit':commit,'dirty':dirty,
                                    'tasks':tasks,'python':sys.version,'acceptance_passed':None})
    reports = []
    try:
        for plan in plans:
            report = execute_plan(plan,directory)
            reports.append({'task':plan['task'],'status':report['status'],
                            'report':str((directory/plan['task'].lower().replace('-','')/'report.json').relative_to(ROOT))})
            print(plan['task'] + ': ' + report['status'],flush=True)
    finally:
        save_json(directory/'summary.json',{'format':'omega-validation-summary-1','results':reports,
                                           'tasks_requested':len(tasks),'tasks_finished':len(reports),
                                           'acceptance_passed':None,'independent_review':None})
    return 0 if len(reports)==len(tasks) and all(r['status']=='checks_passed_acceptance_pending' for r in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
