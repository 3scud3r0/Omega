"""Axiom/dependency admission consumes checker output from the trusted Lean process."""
import re
DEFAULT=frozenset({'propext','Classical.choice','Quot.sound'})
def inspect_output(output,expected,allowed=DEFAULT):
    if type(output) is not str or len(output)>4*1024**2:raise ValueError('Invalid checker transcript')
    found={}
    for name,body in re.findall(r"'([^']+)' depends on axioms: \[([^\]]*)\]",output):
        axioms=frozenset(a.strip() for a in body.split(',') if a.strip())
        if name in found and found[name]!=axioms:raise ValueError('Ambiguous axiom report')
        found[name]=axioms
    if not set(expected)<=set(found):raise ValueError('Missing axiom reports')
    for name in expected:
        if not found[name]<=set(allowed):raise ValueError('Unauthorized axiom: '+name)
    return {name:sorted(found[name]) for name in expected}
def forbid_admissions(source):
    # Conservative prefilter only; kernel/axiom inspection remains authoritative.
    if re.search(r'\b(sorry|admit|axiom)\b',source):raise ValueError('Unapproved proof admission/declaration')
    return source
