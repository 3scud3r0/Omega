from fractions import Fraction as Q
import random
import pytest
from omega_gpu_mcts.flat import FlatBatch
from omega_gpu_mcts.backend import CudaSearch,CudaUnavailable,decode_prefix
from omega_gpu_mcts.build import nvcc
from omega_refine_check.syntax import parse,evaluate


def test_flat_soa_jobs_match_independent_exact_evaluation():
    expressions=['(x+1)*(y-2)','relu(x-y)','1/(x*x+1)','x/y','-x']
    batch=FlatBatch.create(expressions,['x','y'])
    cases=[{'x':str(Q(x,3)),'y':str(Q(y,7))} for x in (-5,0,3) for y in (-2,0,4)]
    observed=batch.evaluate(cases)
    for ast,result in zip(batch.expressions,observed):
        for i,case in enumerate(cases):
            try:expected=evaluate(ast,{k:Q(v) for k,v in case.items()})
            except (ZeroDivisionError,ValueError):assert result['errors'][i]==1
            else:assert result['errors'][i]==0 and result['values'][i]==expected


def test_interval_filter_conservative_rejection_and_overflow():
    batch=FlatBatch.create(['x+1','x*x','1/x','x*9223372036854775807'],['x'])
    result=batch.filter([[-1,1]],[-2,2])
    assert result['admissible']==[True,True,False,False]
    assert result['errors'][2]==1 and not result['formal_admission']
    assert FlatBatch.create(['x*x'],['x']).filter([[-2,2]],[0,4])['admissible']==[False] # dependency loss is not a false proof
    assert FlatBatch.create(['1/x'],['x']).filter([[1,2]],['1/2',1])['admissible']==[True]


def test_corrupted_flat_child_cycle_is_refused_before_read():
    batch=FlatBatch.create(['x+1'],['x'])
    batch.left[2]=2
    assert batch.evaluate([{'x':1}])[0]['errors']==[4]
    assert batch.filter([[0,1]],[0,2])['admissible']==[False]
    with pytest.raises(ValueError):decode_prefix([48,0],['x'],[])
    with pytest.raises(ValueError):decode_prefix([31],['x'],[])


def test_accepted_interval_boxes_contain_sampled_reference_results():
    rng=random.Random(12)
    for _ in range(100):
        lo=rng.randint(-5,0);hi=rng.randint(1,5)
        ast=f'relu((x+{rng.randint(0,3)})*{rng.randint(0,3)})'
        batch=FlatBatch.create([ast],['x']);result=batch.filter([[lo,hi]],[-100,100])
        assert result['admissible']==[True]
        for i in range(7):assert -100<=evaluate(parse(ast),{'x':Q(lo)+(Q(hi-lo)*i/6)})<=100


def test_complete_cuda_pipeline_compiles_and_reports_device_absence():
    try:nvcc()
    except RuntimeError:pytest.skip('CUDA SDK unavailable; pipeline compile pending')
    try:engine=CudaSearch()
    except CudaUnavailable:pytest.skip('CUDA pipeline compiled; device execution pending: no GPU')
    spec={'variables':{'x':'self>=-1 and self<=1'},'ensures':'result==x+1',
          'examples':[{'inputs':{'x':str(x)},'output':str(x+1)} for x in (-1,0,1)]}
    result=engine.search(spec,input_bounds=[[-1,1]],output_bounds=[0,2],rollouts=256,iterations=200)
    assert result['statistics']['candidates']==51200
    assert result['statistics']['nodes_evaluated']>=50000
    assert result['statistics']['elapsed_ms']<1000,'50,000-node GPU latency target was not met on this device'
    assert result['candidates'] and all(not c['formal_admission'] for c in result['candidates'])
