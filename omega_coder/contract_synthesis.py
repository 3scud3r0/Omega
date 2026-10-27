"""Bounded scalar synthesis over exact finite observations, never a proof.

Only data expressions (+, -, *) are enumerated. No generated Python or Omega
source executes here. Native execution belongs to the isolated workflow.
"""
from fractions import Fraction
from itertools import product
import re

MAX_VARIABLES = 32
MAX_CONSTANTS = 64
MAX_EXAMPLES = 256
MAX_RATIONAL_BITS = 256


def rational(value):
    """Reject approximate/bool inputs and cap integers before arithmetic."""
    if type(value) is str:
        if len(value) > 160 or not re.fullmatch(r'-?[0-9]+(?:/[1-9][0-9]*)?', value):
            raise ValueError('Exact integer or rational literal required')
    elif type(value) not in (int, Fraction):
        raise ValueError('Exact integer or rational required; floats/bools are ambiguous')
    if type(value) is int and value.bit_length() > MAX_RATIONAL_BITS:
        raise ValueError('Rational bit budget exceeded')
    result = Fraction(value)
    if max(result.numerator.bit_length(), result.denominator.bit_length()) > MAX_RATIONAL_BITS:
        raise ValueError('Rational bit budget exceeded')
    return result


def variables_contract(variables):
    if type(variables) not in (list, tuple) or len(variables) > MAX_VARIABLES:
        raise ValueError('Bounded variable list required')
    if any(type(v) is not str or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,63}', v)
           for v in variables) or len(set(variables)) != len(variables):
        raise ValueError('Unique scalar identifiers required')
    return tuple(variables)


def observations(variables, examples):
    if type(examples) not in (list, tuple) or not 1 <= len(examples) <= MAX_EXAMPLES:
        raise ValueError('Nonempty bounded finite observations required')
    result = []
    seen = set()
    for example in examples:
        if type(example) not in (list, tuple) or len(example) != 2:
            raise ValueError('Observation must contain an environment and a target')
        env, target = example
        if type(env) is not dict or set(env) != set(variables):
            raise ValueError('Observation variables do not match the contract')
        normalized = {v: rational(env[v]) for v in variables}
        key = tuple(normalized.values())
        if key in seen:
            raise ValueError('Duplicate observation inputs are not independent cases')
        seen.add(key)
        result.append((normalized, rational(target)))
    return tuple(result)


def _evaluate(expression, env):
    if expression[0] == 'var':
        return env[expression[1]]
    if expression[0] == 'const':
        return expression[1]
    a, b = _evaluate(expression[1], env), _evaluate(expression[2], env)
    if expression[0] == '+':
        return a + b
    if expression[0] == '-':
        return a - b
    return a * b


def synthesize(variables, constants, examples, *, max_nodes=7, max_candidates=10000):
    if type(max_nodes) is not int or not 1 <= max_nodes <= 31:
        raise ValueError('Expression node budget must be in [1,31]')
    if type(max_candidates) is not int or not 1 <= max_candidates <= 100000:
        raise ValueError('Candidate budget must be in [1,100000]')
    variables = variables_contract(variables)
    if type(constants) not in (list, tuple) or len(constants) > MAX_CONSTANTS:
        raise ValueError('Bounded constants required')
    constants = tuple(dict.fromkeys(rational(c) for c in constants))
    examples = observations(variables, examples)
    atoms = [('var', v) for v in variables] + [('const', c) for c in constants]
    if not atoms:
        raise ValueError('At least one expression atom required')
    levels = {}
    checked = 0
    for size in range(1, max_nodes + 1, 2):
        level = []
        levels[size] = level
        if size == 1:
            candidates = iter(atoms)
        else:
            candidates = (
                (op, a, b)
                for left in range(1, size - 1, 2)
                for op, a, b in product(('+', '-', '*'), levels[left], levels[size - 1 - left])
            )
        for expression in candidates:
            if checked == max_candidates:
                return None
            checked += 1
            # Retain only examined candidates. The former implementation built
            # whole products before applying the global candidate budget.
            level.append(expression)
            if all(_evaluate(expression, env) == target for env, target in examples):
                return {'expression': expression, 'checked': checked, 'universal': False}
    return None
