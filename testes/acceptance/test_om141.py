"""OM-141: executable checks; source delivery, not a recorded pass."""
from omega_bench.ablations import compare,COMPONENTS
from omega_bench.harness import BenchmarkBudget

def test_ablation_omits_exactly_one_component_and_does_not_authorize_promotion():
    configured=[]
    def configure(enabled):configured.append(enabled);return lambda case,budget,seed:len(enabled)
    result=compare(configure,[{'id':'p','domain':'d','input':0}],lambda id,candidate:candidate==4,BenchmarkBudget(),seed=7)
    assert len(configured)==5 and configured[0]==COMPONENTS and all(len(v)==3 for v in configured[1:])
    assert result['results']['full']['correct']==1 and result['results']['without_lean']['correct']==0
    assert 'does not authorize' in result['warning']
