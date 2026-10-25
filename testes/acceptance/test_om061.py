"""OM-061: executable checks; source delivery, not a recorded pass."""
import ast
from omega_coder.test_generation import Example,generate_python,mutation_score

def test_generated_contract_contains_oracles_and_mutants_are_counted():
    source=generate_python('add',[Example((1,2),3),Example((-1,1),0)])
    tree=ast.parse(source)
    assert len([node for node in ast.walk(tree) if isinstance(node,ast.Assert)])==2
    result=mutation_score([3,4,5],lambda candidate:candidate,lambda value:value==3)
    assert result=={'mutants':3,'killed':2,'score':2/3}
