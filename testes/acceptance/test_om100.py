"""OM-100: executable checks; source delivery, not a recorded pass."""
from omega_bench.neural_symbolic import compare
from omega_bench.harness import BenchmarkBudget

def test_neural_symbolic_comparison_uses_same_cases_and_seeds():
    observed=[]
    def solver(case,budget,seed):observed.append((case['id'],seed));return case['input']
    cases=[{'id':'x','domain':'bool','input':1}]
    result=compare(cases,solver,solver,lambda id,candidate:candidate==1,BenchmarkBudget(cases=1),seed=7)
    assert result['same_cases'] and result['neural']['correct']==result['symbolic']['correct']==1
    assert observed==[('x',7),('x',7)]
