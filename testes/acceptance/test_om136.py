"""OM-136: executable checks; source delivery, not a recorded pass."""
from omega_bench.harness import run,BenchmarkBudget

def test_benchmark_hides_answers_and_preserves_negative_outcomes():
    def solver(public,budget,seed):
        assert set(public)=={'id','domain','input'}
        return public['input']
    cases=[{'id':'a','domain':'d','input':1,'hidden_answer':1},{'id':'b','domain':'d','input':0,'hidden_answer':1}]
    report=run(cases,solver,lambda id,candidate:candidate==1,BenchmarkBudget(),seed=7)
    assert report['cases']==2 and report['correct']==1 and report['accuracy']==.5
    assert [r['status'] for r in report['records']]==['correct','incorrect']
