"""Certified bounded resource transfers as data-only Omega actions.

No shell adapter is provided. A verified transition returns a new immutable
state; external effects still require a host authorization/transaction adapter.
"""
from dataclasses import dataclass
from fractions import Fraction
from omega.certified_proof import check, rational_literal as lit


@dataclass(frozen=True)
class ResourceState:
    balances: tuple[Fraction, ...]
    capacities: tuple[Fraction, ...]
    version: int = 0

    def __post_init__(self):
        object.__setattr__(self, 'balances', tuple(Fraction(v) for v in self.balances))
        object.__setattr__(self, 'capacities', tuple(Fraction(v) for v in self.capacities))
        if (not 1 <= len(self.balances) <= 256 or len(self.balances) != len(self.capacities)
                or type(self.version) is not int or self.version < 0
                or any(not 0 <= a <= b for a, b in zip(self.balances, self.capacities))):
            raise ValueError('Resource invariant violated')


def transfer(state, *, source, destination, amount, expected_version):
    if type(state) is not ResourceState or type(expected_version) is not int or state.version != expected_version:
        raise ValueError('Stale or invalid state')
    if any(type(i) is not int or not 0 <= i < len(state.balances) for i in (source, destination)) or source == destination:
        raise ValueError('Distinct valid resource indices required')
    if type(amount) not in (int, str, Fraction):
        raise ValueError('Exact amount required')
    amount = Fraction(amount)
    if amount <= 0:
        raise ValueError('Positive transfer required')
    after = list(state.balances)
    after[source] -= amount
    after[destination] += amount
    # Validate before emitting either code or a proof.
    successor = ResourceState(tuple(after), state.capacities, state.version + 1)
    lines = ['import ProofPrelude', 'namespace OmegaAction',
             'theorem transfer_preserves (src dst capS capD amount : ℚ)',
             '    (hs : 0 ≤ src ∧ src ≤ capS) (hd : 0 ≤ dst ∧ dst ≤ capD)',
             '    (ha : 0 ≤ amount) (funded : amount ≤ src) (room : dst + amount ≤ capD) :',
             '    (0 ≤ src - amount ∧ src - amount ≤ capS) ∧',
             '    (0 ≤ dst + amount ∧ dst + amount ≤ capD) ∧',
             '    (src - amount) + (dst + amount) = src + dst := by',
             '  refine ⟨⟨sub_nonneg.mpr funded, le_trans (sub_le_self src ha) hs.2⟩,',
             '          ⟨add_nonneg hd.1 ha, room⟩, ?_⟩',
             '  ring', '#print axioms transfer_preserves']
    names = ['OmegaAction.transfer_preserves']
    for i, (balance, capacity) in enumerate(zip(after, state.capacities)):
        lines += [f'theorem invariant_{i} : 0 ≤ {lit(balance)} ∧ {lit(balance)} ≤ {lit(capacity)} := by norm_num',
                  f'#print axioms invariant_{i}']
        names.append(f'OmegaAction.invariant_{i}')
    old_sum, new_sum = sum(state.balances), sum(after)
    lines += [f'theorem conservation : {lit(new_sum)} = {lit(old_sum)} := by norm_num',
              '#print axioms conservation', 'end OmegaAction']
    names.append('OmegaAction.conservation')
    proof = '\n'.join(lines) + '\n'
    admission = check(proof, names)
    # Only exact arithmetic assignments; never arbitrary text from a proposer.
    def q(v):
        return f'({v.numerator}/{v.denominator})'
    program = '\n'.join(f'parametro balance_{i}={q(x)};' for i, x in enumerate(state.balances))
    program += f'\ntensor debit=balance_{source}-{q(amount)};\ntensor credit=balance_{destination}+{q(amount)};\nmostrar debit;\nmostrar credit;\n'
    return successor, {'program': program, 'proof': proof, 'admission': admission,
                       'pre_version': state.version, 'post_version': successor.version,
                       'scope': 'this bounded resource transition; no external side effects'}


def execute_transfer(state, directory, **action):
    """Prove, lower and execute the pure transition before returning its state."""
    from pathlib import Path
    from omega_selfhost.driver import build, run
    successor, evidence = transfer(state, **action)
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    source = root / 'action.omega'
    source.write_text(evidence['program'])
    (root / 'action.lean').write_text(evidence['proof'])
    build(source, root / 'action')
    result, admission = run(root / 'action')
    if (Fraction(result['values']['debit']) != successor.balances[action['source']]
            or Fraction(result['values']['credit']) != successor.balances[action['destination']]):
        raise ValueError('Native transition disagrees with proved successor')
    return successor, {**evidence, 'native_admission': admission}
