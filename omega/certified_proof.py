"""Shared admission for proofs rendered from validated data by this package.

This is a trusted renderer boundary, not an API for accepting untrusted Lean.
"""
import hashlib
import os
from pathlib import Path
import tempfile

from omega_platform.budget import PROOF_BUDGET
from omega_platform.sandbox import trusted
from omega_selfhost.axiom_policy import DEFAULT, forbid_admissions
from omega_selfhost.proof import lake_binary


def rational_literal(value):
    from fractions import Fraction
    q = Fraction(value)
    return f'(({q.numerator} : ℚ) / {q.denominator})'


def check(source, declarations):
    """Require kernel success and an explicit allowed-axiom report per theorem."""
    import re
    forbid_admissions(source)
    if not declarations or len(set(declarations)) != len(declarations):
        raise ValueError('Nonempty unique theorem names required')
    root = Path(os.environ.get('OMEGA_TENSOR_PROJECT', str(Path(__file__).resolve().parents[1] / 'formal/tensor')))
    with tempfile.TemporaryDirectory(prefix='omega-certified-') as tmp:
        path = Path(tmp) / 'Certificate.lean'
        path.write_text(source)
        result = trusted([str(lake_binary()), 'env', 'lean', str(path)],
                         cwd=root, budget=PROOF_BUDGET)
    output = result.stdout + result.stderr
    if not result.ok or 'warning:' in output:
        raise ValueError('Lean rejected certificate: ' + output[-6000:])
    reports = {}
    for name, body in re.findall(r"'([^']+)' depends on axioms: \[([^\]]*)\]", output):
        reports[name] = {s.strip() for s in body.split(',') if s.strip()}
    for name in re.findall(r"'([^']+)' does not depend on any axioms", output):
        reports[name] = set()
    if any(name not in reports or not reports[name] <= DEFAULT for name in declarations):
        raise ValueError('Missing or unauthorized theorem dependencies')
    return {'checker': 'Lean 4.19.0', 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'theorems': list(declarations), 'axioms': {n: sorted(reports[n]) for n in declarations}}
