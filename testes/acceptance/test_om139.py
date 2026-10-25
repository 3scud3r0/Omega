"""OM-139: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_bench.generalization import by_domain
from omega_bench.harness import BenchmarkBudget

def test_generalization_uses_only_domains_outside_training():
    cases=[{'id':'p','domain':'new','input':2}]
    result=by_domain(cases,['old'],lambda public,budget,seed:public['input'],lambda id,candidate:candidate==2,BenchmarkBudget())
    assert result['new']['accuracy']==1
    with pytest.raises(ValueError):by_domain(cases,['new'],lambda *_:0,lambda *_:False,BenchmarkBudget())
