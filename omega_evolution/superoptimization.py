"""Bounded rule search and isolated native self-recompilation.

Only two audited emitter templates are installable. Arbitrary compiler patches
are not admitted by a polynomial identity or a bootstrap fixed point.
"""
import hashlib
import json
from pathlib import Path
import os
from omega_selfhost.proof import check_identities
from omega_selfhost.driver import compiler, cc, PACKAGE, digest
from omega_platform.sandbox import run
from omega_platform.budget import COMPILER_BUDGET


def proposals():
    a, b = ['v', 'a'], ['v', 'b']
    for name, outer, inner in [('add_cancel_right', '-', '+'), ('sub_cancel_right', '+', '-')]:
        yield {'name': name,
               'identity': {'tipo': 'identidade_nativa', 'left': ['bin', outer, ['bin', inner, a, b], b], 'right': a},
               'cost_before': 5, 'cost_after': 1}
    # Deliberately include a cheaper but false candidate. The same Lean gate
    # must reject it; cost alone never admits a rewrite.
    yield {'name': 'invalid_drop_addend',
           'identity': {'tipo': 'identidade_nativa', 'left': ['bin', '+', a, b], 'right': a},
           'cost_before': 3, 'cost_after': 1}


def discover():
    accepted, rejected = [], []
    for proposal in proposals():
        try:
            admission = check_identities([proposal['identity']])
        except (ValueError, RuntimeError) as exc:
            rejected.append({'name': proposal['name'], 'reason': str(exc)})
            continue
        accepted.append({**proposal, 'admission': admission})
    return {'accepted': accepted, 'rejected': rejected}


def _template(name):
    outer, inner = {'add_cancel_right': ('-', '+'), 'sub_cancel_right': ('+', '-')}[name]
    return (f'  se (op=="{outer}" && nodes[a[0]]["op"]=="{inner}") {{ '
            f'var nested=nodes[a[0]]["args"]; se (nested[1]==a[1]) {{ retornar ["{name}",nested[0]]; }} }}\n')


def evolve(directory, *, generations=1):
    """Build a local candidate compiler chain; production checkout is preserved."""
    if type(generations) is not int or not 1 <= generations <= 16:
        raise ValueError('Generation budget must be in [1,16]')
    search = discover()
    if not search['accepted']:
        raise ValueError('No proved rewrite candidates')
    root = Path(directory).absolute()
    root.mkdir(parents=True, exist_ok=False)
    source = (PACKAGE / 'compiler.omega').read_text()
    anchor = '  retornar [];\n}\nfuncao optimize(ir)'
    if source.count(anchor) != 1:
        raise ValueError('Unknown compiler template version')
    current, parent, records = Path(compiler()), digest(PACKAGE / 'compiler.omega'), []
    installed = []
    for generation, rule in enumerate(search['accepted'][:generations], 1):
        installed.append(rule['name'])
        candidate = source.replace(anchor, ''.join(_template(name) for name in installed) + anchor)
        location = root / f'generation-{generation}'
        location.mkdir()
        path = location / 'compiler.omega'
        path.write_text(candidate)
        c1, c2, c3 = [location / f'stage{i}.c' for i in (1, 2, 3)]
        bin1, bin2 = location / 'stage1', location / 'stage2'
        for tool, output, binary in ((current, c1, bin1), (bin1, c2, bin2)):
            run([tool, path, output], readonly=[path], writable=[location], budget=COMPILER_BUDGET, check=True)
            cc(output, binary)
        run([bin2, path, c3], readonly=[path], writable=[location], budget=COMPILER_BUDGET, check=True)
        if c2.read_bytes() != c3.read_bytes():
            raise ValueError('Candidate compiler did not reach a native fixed point')
        # Exercise the newly admitted rule, including the independent gradient proof.
        sample = location / 'probe.omega'
        expression = '(a+b)-b' if rule['name'] == 'add_cancel_right' else '(a-b)+b'
        sample.write_text(f'parametro a=2; parametro b=3; perda y={expression}; gradiente y em a; mostrar y;\n')
        out = location / 'probe.c'
        run([bin2, sample, out, '--optimize'], readonly=[sample], writable=[location], budget=COMPILER_BUDGET, check=True)
        witness = json.loads(Path(str(out) + '.opt.json').read_text())
        if not any(r['regra'] == rule['name'] for r in witness['regras']):
            raise ValueError('Candidate compiler did not apply its new rule')
        from omega_selfhost.driver import verify_optimization
        proof = verify_optimization(witness, proof_path=location / 'rewrite.lean')
        from omega_selfhost.proof_protocol import encode
        record = {'generation': generation, 'parent': parent, 'source_sha256': digest(path),
                  'binary_sha256': digest(bin2), 'rule': rule['name'], 'proof': proof,
                  'fixed_point': True, 'previous_record': records[-1]['sha256'] if records else None}
        record['sha256'] = hashlib.sha256(encode(record)).hexdigest()
        records.append(record)
        parent, current = record['source_sha256'], bin2
    report = {'format': 'omega-certified-evolution-1', 'generations': records,
              'compiler': str(current), 'production_promoted': False,
              'requested_generations': generations,
              'stopping_reason': 'generation budget' if len(records) == generations else 'audited rule templates exhausted',
              'scope': 'proved value/gradient rewrites and native fixed points; trusted emitter templates'}
    (root / 'lineage.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    # Publish only the local experiment pointer, after every gate has passed.
    pointer = root / '.current.tmp'
    pointer.write_text(str(current.relative_to(root)) + '\n')
    os.replace(pointer, root / 'current')
    return report


def audit(directory, *, expected_head_sha256):
    """Audit a chain against an externally retained head digest, without execution."""
    from omega_selfhost.proof_protocol import encode
    from omega_selfhost.driver import verify_optimization
    root = Path(directory)
    report = json.loads((root / 'lineage.json').read_text())
    records = report['generations']
    if not records or records[-1]['sha256'] != expected_head_sha256:
        raise ValueError('Unrelated evolution chain')
    source = (PACKAGE / 'compiler.omega').read_text()
    anchor = '  retornar [];\n}\nfuncao optimize(ir)'
    installed, previous = [], None
    parent = digest(PACKAGE / 'compiler.omega')
    for i, original in enumerate(records, 1):
        record = dict(original)
        claimed = record.pop('sha256')
        if hashlib.sha256(encode(record)).hexdigest() != claimed:
            raise ValueError('Changed generation record')
        if record['generation'] != i or record['previous_record'] != previous or record['parent'] != parent:
            raise ValueError('Broken evolution ancestry')
        installed.append(record['rule'])
        location = root / f'generation-{i}'
        candidate = source.replace(anchor, ''.join(_template(name) for name in installed) + anchor)
        if (location / 'compiler.omega').read_text() != candidate:
            raise ValueError('Unaudited compiler source changes')
        if digest(location / 'compiler.omega') != record['source_sha256'] or digest(location / 'stage2') != record['binary_sha256']:
            raise ValueError('Changed compiler artifact')
        if (location / 'stage2.c').read_bytes() != (location / 'stage3.c').read_bytes():
            raise ValueError('Broken native fixed point')
        witness = json.loads((location / 'probe.c.opt.json').read_text())
        verify_optimization(witness)
        parent, previous = record['source_sha256'], claimed
    return {'valid': True, 'generations': len(records), 'head_sha256': previous,
            'scope': 'pinned lineage and admitted rewrites; no arbitrary compiler refinement claim'}
