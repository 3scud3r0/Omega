from fractions import Fraction as Q
import math,random,subprocess
import pytest
from omega_gpu_mcts.numeric import Numeric
from omega_gpu_mcts.build import compile_cuda,ROOT,nvcc


@pytest.fixture(scope='module')
def numeric():return Numeric(sanitize=True)


def test_shared_rational_alu_matches_independent_fraction(numeric):
    rng=random.Random(912)
    for _ in range(2500):
        a=Q(rng.randint(-10**6,10**6),rng.randint(1,10**6));b=Q(rng.randint(-10**6,10**6),rng.randint(1,10**6))
        for op,expected in [('+',a+b),('-',a-b),('*',a*b),('/',a/b if b else None)]:
            if expected is not None:assert numeric.operation(op,a,b)==expected
        x=rng.getrandbits(64);y=rng.getrandbits(64)
        assert numeric.gcd(x,y)==math.gcd(x,y)


def test_pruning_including_large_intermediate_error_products(numeric):
    rng=random.Random(21)
    cases=[(Q(355,113),100),(Q(-1,2),1),(Q(0),1)]
    cases += [(Q(rng.randint(-(2**63-1),2**63-1),rng.randint(1,2**63-1)),rng.randint(1,2**63-1)) for _ in range(1000)]
    for q,cap in cases:
        value,error=numeric.prune(q,cap)
        assert value==q.limit_denominator(cap) and error==abs(q-value)


def test_overflow_and_zero_division_are_explicit(numeric):
    with pytest.raises(OverflowError):numeric.operation('+',2**63-1,1)
    with pytest.raises(ZeroDivisionError):numeric.operation('/',1,0)
    assert numeric.operation('*',Q(2**63-1,2),Q(2,2**63-1))==1
    assert numeric.gcd(0,0)==0 and numeric.gcd(0,2**64-1)==2**64-1


def test_cuda_numeric_target_compiles_and_ten_million_ops_if_device(tmp_path):
    try:nvcc()
    except RuntimeError:pytest.skip('CUDA SDK unavailable: CUDA compilation and device stress pending')
    binary=compile_cuda([ROOT/'testes/cuda/rational_stress.cu'],tmp_path/'stress')
    result=subprocess.run([binary,'10000000'],capture_output=True,text=True,timeout=300)
    if result.returncode==77:pytest.skip('CUDA target compiled; 10,000,000 device operations pending: no GPU')
    assert result.returncode==0,result.stderr
    assert '10000000' in result.stdout
