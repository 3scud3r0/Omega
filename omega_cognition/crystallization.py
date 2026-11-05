"""Portable, statement-bound crystallization; verification never executes received code."""
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

from . import bridge
from .problem import normalize, flat
from .statistics import confidence, probability
from omega_refine_check.syntax import tree,render

FILES = {
    'hypothesis.json': 128*1024,
    'empirical.json': 256*1024,
    'formal/hypothesis.lean': 256*1024,
    'formal/receipt.json': 512*1024,
    'native/specialization.omega': 128*1024,
    'native/compiler.elf': 1024*1024,
    'native/candidate.elf': 1024*1024,
    'receipt.stark': 4*1024*1024,
    'zk.json': 256*1024,
}
SCOPES = ['Lean rational expression theorem', 'RV64 closed specialization',
          'RV32IM checked-u32 execution STARK; not RV64 compiler correctness']


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(root, name, limit):
    """Read bounded regular files with no symlinks, including intermediate dirs."""
    parts = name.split('/')
    if any(p in ('', '.', '..') for p in parts):
        raise ValueError('Unsafe crystallization path')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory); directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
                raise ValueError('Crystallization file type/size')
            raw = stream.read(limit+1)
        if len(raw) > limit:
            raise ValueError('Crystallization byte budget')
        return raw
    finally:
        os.close(directory)


def decode(raw):
    from omega_security.encoding import decode as bounded_decode
    return bounded_decode(raw, max_bytes=512*1024, max_nodes=50000, max_depth=64)


def publish(directory, *, empirical=True):
    """Bind existing, already checked artifacts. Hashes alone do not verify them."""
    root = Path(directory)
    files = {k: v for k, v in FILES.items() if empirical or k != 'empirical.json'}
    assets = {name: hashlib.sha256(read(root, name, limit)).hexdigest() for name, limit in files.items()}
    hypothesis = decode(read(root, 'hypothesis.json', FILES['hypothesis.json']))
    manifest = {'format': 'omega-crystallization-1', 'problem_sha256': digest(hypothesis['problem']),
                'assets': assets, 'empirical': empirical, 'kernel_activated': False,
                'promotion': 'pending_independent_approval',
                'scopes': SCOPES}
    manifest['sha256'] = digest(manifest)
    destination = root/'crystallization.json'
    with destination.open('x') as stream:
        stream.write(json.dumps(manifest, sort_keys=True, indent=2)+'\n')
    return manifest


def verify(manifest_path, expected_problem, *, verifier, replay_empirical=False,
           max_alpha='0.05', max_epsilon='0.00001', require_empirical=True):
    """Rebuild the statement from the caller's expected problem, check Lean,
    regenerate RV64 in isolation and independently verify the real receipt.
    Returned scope never includes promotion or a whole-compiler theorem.
    """
    path = Path(manifest_path).absolute()
    if path.name != 'crystallization.json':
        raise ValueError('Expected crystallization.json')
    root = path.parent
    manifest = decode(read(root, path.name, 128*1024))
    required = {'format', 'problem_sha256', 'assets', 'empirical', 'kernel_activated', 'promotion', 'scopes', 'sha256'}
    if type(manifest) is not dict or set(manifest) != required:
        raise ValueError('Crystallization manifest schema')
    unsigned = {k:v for k,v in manifest.items() if k != 'sha256'}
    if (manifest['format'] != 'omega-crystallization-1' or digest(unsigned) != manifest['sha256']
            or type(manifest['empirical']) is not bool or manifest['kernel_activated'] is not False
            or manifest['scopes'] != SCOPES
            or manifest['promotion'] != 'pending_independent_approval'):
        raise ValueError('Crystallization integrity/promotion policy')
    if require_empirical and not manifest['empirical']:
        raise ValueError('Empirical evidence required for bicameral verification')
    names = set(FILES) - (set() if manifest['empirical'] else {'empirical.json'})
    if type(manifest['assets']) is not dict or set(manifest['assets']) != names:
        raise ValueError('Crystallization assets schema')
    assets = {name:read(root, name, FILES[name]) for name in sorted(names)}
    if any(hashlib.sha256(raw).hexdigest() != manifest['assets'][name] for name,raw in assets.items()):
        raise ValueError('Crystallization artifact hash mismatch')
    problem = normalize(expected_problem)
    hypothesis = decode(assets['hypothesis.json'])
    if (type(hypothesis) is not dict or set(hypothesis) != {'format','problem','candidate','ast'}
            or hypothesis['format'] != 'omega-cognitive-hypothesis-1'
            or digest(expected_problem) != manifest['problem_sha256']
            or hypothesis['problem'] != expected_problem):
        raise ValueError('Crystallization statement differs from expected problem')
    candidate = tree(hypothesis['ast'])
    if render(candidate) != hypothesis['candidate']:
        raise ValueError('Hypothesis AST and expression differ')
    flat(candidate, list(problem['grid']))
    source, _ = bridge.hypothesis_to_lemma(candidate, problem)
    if assets['formal/hypothesis.lean'] != source.encode():
        raise ValueError('Lean certificate is unrelated to the hypothesis')
    evidence = None
    if manifest['empirical']:
        evidence = decode(assets['empirical.json'])
        assessment = evidence['confidence']
        actual = confidence(evidence['counts']['iid'], evidence['failures']['iid'],
                            alpha=assessment['alpha'], epsilon=assessment['epsilon'])
        if (actual != assessment or not actual['accepted'] or not evidence['accepted']
                or any(evidence['failures'].values()) or evidence['formal_admission'] is not False
                or evidence['candidate_sha256'] != digest(flat(candidate,list(problem['grid'])))
                or probability(actual['alpha']) > probability(max_alpha)
                or probability(actual['epsilon']) > probability(max_epsilon)):
            raise ValueError('Empirical evidence fails requested confidence policy')
        if replay_empirical:
            from .debate import evaluate
            replay = evaluate(candidate, problem, trials=evidence['counts']['iid'],
                              alpha=assessment['alpha'], epsilon=assessment['epsilon'],
                              seed=evidence['validation_seed'], wall_seconds=3600)
            for field in ('candidate_sha256','counts','failures','confidence','transcript_sha256'):
                if replay[field] != evidence[field]:
                    raise ValueError('Empirical replay mismatch: '+field)
    with tempfile.TemporaryDirectory(prefix='omega-crystallization-check-') as tmp:
        temporary = Path(tmp)
        proof = bridge.prove(candidate, problem, temporary/'formal')
        if proof != decode(assets['formal/receipt.json']):
            raise ValueError('Lean admission receipt mismatch')
        native = bridge.emit_rv64(candidate, problem, temporary/'native')
        for name in ('specialization.omega','compiler.elf','candidate.elf'):
            if (temporary/'native'/name).read_bytes() != assets['native/'+name]:
                raise ValueError('Native specialization differs from independent rebuild')
    from omega_zk.execution import Engine
    checker = Engine(verifier)
    program = bridge.zk_specialization(candidate, problem, checker)
    identity = checker.image_id(program)
    zk = decode(assets['zk.json'])
    if (type(zk) is not dict or 'image_id' not in zk or 'journal' not in zk
            or zk['image_id'] != identity or zk['journal'] != program.journal.decode()):
        raise ValueError('STARK statement differs from independently compiled hypothesis')
    receipt = checker.verify(assets['receipt.stark'], identity, program.journal)
    return {'format':'omega-crystallization-verification-1','verified':True,
            'manifest_sha256':manifest['sha256'],'problem_sha256':digest(expected_problem),
            'formal':proof['admission'],'native':native,'stark':receipt,
            'empirical_replayed':bool(evidence is not None and replay_empirical),
            'kernel_activated':False,'promotion':'pending_independent_approval'}
