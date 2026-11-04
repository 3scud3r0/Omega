"""Bounded MCTS → Lean → four-stage bootstrap → independent promotion gate.

No compiler, kernel, worktree or running process is replaced automatically.
Promotion requires an external signature bound to this exact binary and to
subject-labelled JUnit evidence. The existing bootstrap still uses C/GMP.
"""
from hashlib import sha256
from pathlib import Path
import xml.etree.ElementTree as ET
from omega_security.encoding import canonical,decode
from omega_self_mutate.rules import discover_rule
from omega_self_mutate.bootstrap import evolve
from omega_self_mutate.activation import audit_generation,activate
from omega_selfhost.driver import compiler
from omega_sovereign.models import call


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def prepare(directory,*,lhs='(x*2)-x',iterations=128):
    root=Path(directory).resolve()
    if root.exists():raise FileExistsError(root)
    root.mkdir(parents=True)
    baseline=compiler();base=digest(baseline)
    rule=discover_rule(lhs,iterations=iterations,seed=0)
    record=evolve(rule,root/'generation',activate_default=False)
    candidate=Path(record['bootstrap']['binary'])
    report={'format':'omega-ouroboros-prepared-1','base_sha256':base,
            'candidate_sha256':digest(candidate),'proof_sha256':digest(root/'generation/optimization.lean'),
            'cost_before':record['objective']['before'],'cost_after':record['objective']['after'],
            'proof_kind':'lean-universal-rewrite','metric':'generated-probe-ir-nodes',
            'fixed_point':record['bootstrap']['fixed_point'],'promoted':False,
            'full_candidate_regression_passed':False,'bootstrap_uses_c_gmp':True}
    (root/'prepared.json').write_bytes(canonical(report))
    return report


def signing(e):
    return ('omega-ouroboros-v1|'+e['base_sha256']+'|'+e['candidate_sha256']+'|'+e['proof_sha256']+'|'+e['regression_sha256']+
            '|'+str(e['cost_before'])+'|'+str(e['cost_after'])+'|'+str(e['tests_passed'])+'|'+str(e['failures'])).encode()


def promote(directory,regression,receipt,signature,*,verifier_key,proposer_key,selection_root,minimum_tests=1359):
    """Pre: independent verifier policy, subject-bound results, immutable bundle.

    Post: the existing audited selector atomically chooses the candidate only
    after all gates pass; this does not assert universal performance improvement.
    """
    if type(minimum_tests) is not int or minimum_tests<1359:raise ValueError('Full regression floor 1359')
    root=Path(directory).resolve();record=audit_generation(root/'generation')
    prepared=decode((root/'prepared.json').read_bytes())
    candidate=root/'generation'/record['compiler_relative']
    # Independent receipt cannot rename the subject or reuse a prior baseline.
    for field,value in {'base_sha256':digest(compiler()),'candidate_sha256':digest(candidate),
                        'proof_sha256':digest(root/'generation/optimization.lean'),
                        'regression_sha256':digest(regression)}.items():
        if receipt.get(field)!=value:raise ValueError('Ouroboros subject mismatch: '+field)
        if field!='regression_sha256' and prepared.get(field)!=value:raise ValueError('Modified preparation')
    xml=ET.fromstring(Path(regression).read_bytes())
    properties=[p for p in xml.iter('property') if p.attrib.get('name')=='omega.candidate.sha256']
    if not properties or any(p.attrib.get('value')!=receipt['candidate_sha256'] for p in properties):
        raise ValueError('Candidate-labelled regression evidence required')
    suites=list(xml.iter('testsuite'))
    failures=sum(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0)) for s in suites)
    passed=sum(int(s.attrib.get('tests',0))-int(s.attrib.get('failures',0))-int(s.attrib.get('errors',0))-int(s.attrib.get('skipped',0)) for s in suites)
    if failures or passed<minimum_tests or receipt['failures']!=failures or receipt['tests_passed']!=passed:
        raise ValueError('Ouroboros regression barrier')
    policy={'verifier_key':verifier_key,'proposer_key':proposer_key,'base_sha256':receipt['base_sha256'],'minimum_tests':minimum_tests}
    checked=call('ouroboros',{'policy':policy,'evidence':receipt,'signature':signature})
    if checked['admitted']!=1:raise PermissionError('Independent admission rejected')
    selected=activate(root/'generation',selection_root=Path(selection_root).resolve())
    return {'admission':checked,'selection':selected,'running_process_replaced':False}
