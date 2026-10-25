"""OM-140: executable checks; source delivery, not a recorded pass."""
from omega_bench.longitudinal import generations
from omega_bench.harness import BenchmarkBudget

def test_longitudinal_measurement_pairs_versions_under_identical_seed_and_budget():
    cases=[{'id':'p','domain':'d','input':1}]
    result=generations(['v0','v1'],cases,lambda version:lambda public,budget,seed:int(version=='v1'),lambda id,candidate:candidate==1,BenchmarkBudget(cases=1),seed=7)
    assert [row['measurement']['accuracy'] for row in result]==[0,1]
    assert result[1]['delta_accuracy']==1 and all(row['fixed_seed']==7 for row in result)
