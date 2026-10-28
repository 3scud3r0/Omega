"""Bounded hypothesis -> explicit finite specification -> native synthesis.

Natural language is provenance only. It cannot silently become a specification;
the caller must supply an exact finite Boolean table or rational examples.
"""
from omega_nextorch.gate import certify as boolean_certify, validate_domain


def distill_boolean(hypothesis, task, directory, *, max_size=9, max_candidates=10000):
    from pathlib import Path
    import json
    from omega_nextorch.lean import check
    from omega_nextorch.native import build
    if type(hypothesis) is not str or not 1 <= len(hypothesis) <= 16384:
        raise ValueError('Bounded hypothesis provenance required')
    # Reuse the exhaustive gate and enumerator, not evaluation of LLM text.
    validate_domain(task)
    if type(max_size) is not int or not 1 <= max_size <= 15 or type(max_candidates) is not int or not 1 <= max_candidates <= 100000:
        raise ValueError('Invalid finite search budget')
    rows = len(task['outputs'])
    mask = (1 << rows) - 1
    target = sum(int(b) << i for i, b in enumerate(task['outputs']))
    levels, seen, checked, found = {}, set(), 0, None
    for size in range(1, max_size + 1):
        candidates = []
        if size == 1:
            candidates = [(0, ['c', 0]), (mask, ['c', 1])]
            candidates += [(sum(((r >> j) & 1) << r for r in range(rows)), ['v', j]) for j in range(task['arity'])]
        else:
            candidates += [(mask ^ bits, ['not', ast]) for bits, ast in levels.get(size - 1, [])]
            for a in range(1, size - 1):
                for x, left in levels.get(a, []):
                    for y, right in levels.get(size - 1 - a, []):
                        candidates += [(x & y, ['and', left, right]), (x | y, ['or', left, right]), (x ^ y, ['xor', left, right])]
                        if len(candidates) >= max_candidates:
                            break
                    if len(candidates) >= max_candidates:
                        break
                if len(candidates) >= max_candidates:
                    break
        levels[size] = []
        for bits, ast in candidates:
            checked += 1
            if checked > max_candidates:
                raise ValueError('Finite search candidate budget exhausted')
            if bits == target:
                found = ast
                break
            if bits not in seen:
                seen.add(bits)
                levels[size].append((bits, ast))
        if found is not None:
            break
    if found is None:
        raise ValueError('No circuit within the search budget')
    certificate = boolean_certify(task, found, 'bounded inverse distillation')
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    admission = check(certificate, destination=root / 'circuit.lean')
    native = build(certificate, root / 'circuit')
    (root / 'certificate.json').write_text(json.dumps(certificate, sort_keys=True, indent=2) + '\n')
    return {'certificate': certificate, 'admission': admission, 'native': native,
            'hypothesis': hypothesis, 'checked_candidates': checked,
            'scope': 'complete finite Boolean table only; minimal in the enumerated grammar'}


def distill_rational(hypothesis, problem, directory, **budgets):
    if type(hypothesis) is not str or not 1 <= len(hypothesis) <= 16384:
        raise ValueError('Bounded hypothesis provenance required')
    from omega_coder.native_synthesis import run
    return run(problem, directory, **budgets)
