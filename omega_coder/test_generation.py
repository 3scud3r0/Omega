"""Product API generating reviewable test source, not running generated code."""
import ast,json
from dataclasses import dataclass
@dataclass(frozen=True)
class Example:
    arguments: tuple
    expected: object
def generate_python(function,examples):
    if not function.isidentifier():raise ValueError('Python function identifier required')
    examples=tuple(examples)
    if not 1<=len(examples)<=256:raise ValueError('Example budget exceeded')
    lines=['def test_generated_contract():']
    for example in examples:
        # literal roundtrip prevents executable objects from entering generated source.
        arguments=ast.literal_eval(repr(example.arguments));expected=ast.literal_eval(repr(example.expected))
        lines.append('    assert '+function+'(*'+repr(arguments)+') == '+repr(expected))
    return '\n'.join(lines)+'\n'
def mutation_score(mutations,isolated_runner,oracle):
    killed=0;total=0
    for candidate in mutations:
        if total>=256:raise ValueError('Mutation budget exceeded')
        observation=isolated_runner(candidate)
        if oracle(observation) is False:killed+=1
        total+=1
    return {'mutants':total,'killed':killed,'score':killed/total if total else None}
