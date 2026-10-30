"""Source-bound native scientific applications with explicit OS budgets."""
from pathlib import Path
from fractions import Fraction
import fcntl
import hashlib
import json
import os
import re
import tempfile

from omega.modules import link
from omega_native.codec import decode
from omega_platform.budget import COMPILER_BUDGET, Budget
from omega_platform.sandbox import run as isolated_run
from omega_security.encoding import decode as bounded_decode, canonical
from omega_selfhost.driver import compiler, cc
from omega_selfhost.axiom_policy import DEFAULT, forbid_admissions

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT if (ROOT/'ciencia/catalogo.json').is_file() else ROOT/'omega_native/_sources'
GROUPS = frozenset({'fisica', 'quimica', 'biologia', 'matematica', 'engenharia', 'agentes', 'infraestrutura'})
RUNTIME_INPUTS = ('omega_selfhost/runtime.h', 'omega_selfhost/native_std.h',
                  'omega_selfhost/memory.h', 'omega_selfhost/driver.py',
                  'omega_platform/sandbox.py', 'omega_platform/budget.py',
                  'omega_platform/manifest.py', 'omega_science/runtime.py')
REQUEST_LIMIT = 4 * 1024**2


def catalog():
    value = bounded_decode((SOURCE_ROOT / 'ciencia/catalogo.json').read_bytes(), max_bytes=2*1024**2, max_nodes=30000)
    if value.get('format') != 'omega-science-catalog-1':
        raise ValueError('Unknown scientific catalog')
    entries = value['files']
    if len(entries) != 115 or sorted(x['id'] for x in entries) != list(range(1, 116)):
        raise ValueError('Scientific inventory must contain exactly the 115 declared IDs')
    return value


def kernel(identifier):
    if type(identifier) is not int:
        raise ValueError('Integer scientific kernel ID required')
    for entry in catalog()['files']:
        if entry['id'] == identifier and entry['kind'] == 'native':
            return entry
    raise ValueError('ID does not name a native scientific kernel')


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024**2), b''):
            digest.update(data)
    return digest.hexdigest()


def build(group, destination=None):
    if group not in GROUPS:
        raise ValueError('Known scientific application group required')
    linked = link('ciencia/apps/' + group + '.omega', SOURCE_ROOT, dynamic=True)
    native_compiler = compiler()
    inputs = {name: _hash(ROOT / name) for name in RUNTIME_INPUTS}
    inputs['compiler_binary'] = _hash(native_compiler)
    inputs['bootstrap_manifest'] = _hash(native_compiler.parent / 'bootstrap.json')
    closure = canonical(linked.manifest(), max_bytes=4*1024**2, max_nodes=100000)
    subject = hashlib.sha256(linked.source.encode() + closure + canonical(inputs)).hexdigest()
    cache = ROOT / 'build/science'
    cache.mkdir(parents=True, exist_ok=True)
    target = Path(destination).absolute() if destination else cache / (group + '-' + subject[:32])
    target.parent.mkdir(parents=True, exist_ok=True)
    paths = [target, target.with_suffix('.c'), target.with_suffix('.modules.json'), target.with_suffix('.science.json')]
    with (cache / '.build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if any(p.exists() or p.is_symlink() for p in paths):
            if destination:
                raise FileExistsError('Scientific build destination already exists')
            if any(not p.is_file() or p.is_symlink() for p in paths):
                raise ValueError('Scientific cache is incomplete or redirects through symlinks')
            record = bounded_decode(paths[3].read_bytes(), max_bytes=1024**2)
            if record.get('inputs') != inputs or record.get('subject_sha256') != subject:
                raise ValueError('Scientific cache source mismatch')
            if record.get('binary_sha256') != _hash(target) or record.get('c_sha256') != _hash(paths[1]):
                raise ValueError('Scientific cached binary/C was modified')
            if bounded_decode(paths[2].read_bytes(), max_bytes=4*1024**2, max_nodes=100000) != linked.manifest():
                raise ValueError('Scientific cache module manifest mismatch')
            return target
        with tempfile.TemporaryDirectory(prefix='.science-', dir=target.parent) as tmp:
            folder = Path(tmp)
            source = folder / 'linked.omega'
            source.write_text(linked.source)
            c_source = folder / 'program.c'
            binary = folder / 'program'
            isolated_run([native_compiler, source, c_source], readonly=[source], writable=[folder],
                         budget=COMPILER_BUDGET, check=True)
            cc(c_source, binary)
            record = {'format': 'omega-science-build-1', 'subject_sha256': subject,
                      'inputs': inputs, 'binary_sha256': _hash(binary), 'c_sha256': _hash(c_source),
                      'inference': 'runtime tag/domain checks; no static scientific type proof',
                      'formal_admission': False}
            binary.replace(target)
            c_source.replace(paths[1])
            with paths[2].open('xb') as stream:
                stream.write(canonical(linked.manifest(), max_bytes=4*1024**2, max_nodes=100000))
            with paths[3].open('xb') as stream:
                stream.write(canonical(record))
    return target


def _plain(value, depth=0, meter=None):
    if meter is None:
        meter = [50000, REQUEST_LIMIT]
    meter[0] -= 1
    if meter[0] < 0:
        raise ValueError('Scientific request structure budget')
    if depth > 40:
        raise ValueError('Scientific request nesting budget')
    if type(value) is Fraction:
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > 8192:
            raise ValueError('Scientific rational input budget')
        return _plain(str(value), depth, meter)
    if type(value) is int:
        if value.bit_length() > 8192:
            raise ValueError('Scientific integer input budget')
        return value
    if type(value) is str:
        if len(value) > meter[1]:
            raise ValueError('Scientific request byte budget')
        meter[1] -= len(value.encode('utf-8'))
        if meter[1] < 0:
            raise ValueError('Scientific request byte budget')
        return value
    if type(value) is list:
        if len(value) > meter[0]:
            raise ValueError('Scientific request structure budget')
        return [_plain(x, depth+1, meter) for x in value]
    if type(value) is dict:
        if 2*len(value) > meter[0]:
            raise ValueError('Scientific request structure budget')
        if any(type(k) is not str for k in value):
            raise ValueError('Scientific object keys must be strings')
        return {_plain(k, depth+1, meter): _plain(v, depth+1, meter) for k, v in value.items()}
    raise ValueError('Scientific requests contain exact numbers, strings, arrays and objects; no floats/bools/null')


def run(identifier, request, *, budget=COMPILER_BUDGET):
    entry = kernel(identifier)
    if type(request) is not dict or type(budget) is not Budget:
        raise ValueError('Scientific object request and OS budget required')
    # Count structure before conversion/serialization, including repeated aliases.
    # Fractions are strings at this data boundary, not floating point values.
    plain = _plain(request)
    data = canonical(plain, max_bytes=REQUEST_LIMIT, max_nodes=50000, max_depth=40)
    binary = build(entry['group'])
    with tempfile.TemporaryDirectory(prefix='omega-science-request-') as tmp:
        path = Path(tmp) / 'request.json'
        path.write_bytes(data)
        outcome = isolated_run([binary, str(identifier), path], readonly=[path], budget=budget, check=True)
    if len(outcome.stdout.encode()) > budget.output_bytes:
        raise ValueError('Scientific output budget')
    # Native output is a canonical tagged rational document, never executable code.
    result = decode(outcome.stdout.strip())
    return result


def inspect_lean_transcript(output, expected):
    if type(output) is not str or len(output) > 4*1024**2:
        raise ValueError('Bounded Lean transcript required')
    records = {}
    for name, body in re.findall(r"'([^']+)' depends on axioms: \[([^\]]*)\]", output):
        axioms = {x.strip() for x in body.split(',') if x.strip()}
        if name in records and records[name] != axioms:
            raise ValueError('Ambiguous scientific theorem dependency report')
        records[name] = axioms
    for name in re.findall(r"'([^']+)' does not depend on any axioms", output):
        if name in records and records[name]:
            raise ValueError('Ambiguous scientific theorem dependency report')
        records[name] = set()
    if set(records) != set(expected) or any(not records[name] <= DEFAULT for name in expected):
        raise ValueError('Missing, extra, or unauthorized scientific proof dependencies')
    return {name: sorted(records[name]) for name in expected}


def prove(request, directory):
    """Actually check native-generated closed numeric obligations in Lean CPU.

    This verifies the reconstructed numeric statements. Scientific-model truth,
    correspondence to a source experiment and general C refinement are separate.
    """
    from omega_selfhost.proof import lake_binary
    from omega_platform.budget import PROOF_BUDGET
    from omega_platform.sandbox import trusted
    if type(request) is not dict:
        raise ValueError('Scientific proof object request required')
    # Bind all subsequent counts and hashes to the data actually rendered and
    # checked, even if the caller reuses/mutates its original object concurrently.
    request = _plain(request)
    job = run(104, request)
    source = job['value']
    if hashlib.sha256(source.encode()).hexdigest() != job['source_sha256']:
        raise ValueError('Native scientific proof job/source mismatch')
    forbid_admissions(source)
    expected = re.findall(r'^theorem (science_observation_\d+) :', source, re.MULTILINE)
    if len(expected) != len(request['witnesses']) or not 1 <= len(expected) <= 32:
        raise ValueError('Scientific obligation count mismatch')
    directory = Path(directory).absolute()
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / 'Observation.lean'
    path.write_text(source)
    # Importing only the trusted native template prevents caller tactic/plugin injection.
    status = trusted([lake_binary(), 'env', 'lean', '--root='+str(directory.resolve()),
                      '-o', directory/'Observation.olean', path],
                     cwd=ROOT/'formal/tensor', budget=PROOF_BUDGET)
    output = status.stdout + status.stderr
    (directory/'lean.log').write_text(output)
    if not status.ok or not (directory/'Observation.olean').is_file():
        raise ValueError('Lean rejected scientific numeric obligations; partial evidence retained')
    dependencies = inspect_lean_transcript(output, expected)
    receipt = {'format': 'omega-science-numeric-proof-1', 'verified': True,
               'source_sha256': _hash(path), 'olean_sha256': _hash(directory/'Observation.olean'),
               'lean_sha256': _hash(lake_binary().with_name('lean')),
               'project_manifest_sha256': _hash(ROOT/'formal/tensor/lake-manifest.json'),
               'request_sha256': hashlib.sha256(canonical(_plain(request))).hexdigest(),
               'theorems': dependencies, 'scope': 'closed numeric statements only',
               'scientific_model_accepted': False, 'origin_authenticated': False}
    (directory/'receipt.json').write_bytes(canonical(receipt))
    return receipt
