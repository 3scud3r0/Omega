"""Scientific oracles and adversarial contracts against native Omega execution."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from functools import lru_cache
from itertools import permutations
import hashlib
import json
from pathlib import Path
from collections import Counter
import pytest

from omega_science.runtime import ROOT, catalog, run, _plain
from omega_native.codec import canonical
from omega_platform.sandbox import ExecutionFailure

ENTRIES = {e['id']: e for e in catalog()['files'] if e['kind'] == 'native'}


@lru_cache(None)
def example(identifier):
    return run(identifier, ENTRIES[identifier]['example'])


@pytest.mark.parametrize('identifier', sorted(ENTRIES))
def test_every_declared_native_kernel_actually_executes(identifier):
    value = example(identifier)
    assert type(value) is dict
    if 'formal_admission' in value:
        assert value['formal_admission'] == 0


def test_exact_quadratic_hamiltonian_and_verlet_modified_energy():
    original = dict(position=Q(2,3), momentum=Q(-3,5), mass=Q(7,4), spring=Q(5,2), step=Q(1,7))
    result = run(1, original)
    energy = original['momentum']**2/(2*original['mass'])+original['spring']*original['position']**2/2
    assert result['energy_before'] == energy == result['energy_after']
    verlet = run(2, original)
    inverse = run(2, {**original, 'position': verlet['value'][0], 'momentum': verlet['value'][1], 'step': -original['step']})
    assert inverse['value'] == [original['position'], original['momentum']]
    assert inverse['modified_energy'] == verlet['modified_energy']
    assert verlet['physical_energy_change'] != 0


def test_kepler_bracket_against_independent_decimal_sine():
    lo, hi = example(3)['value']
    def decimal(q):
        return Decimal(q.numerator)/Decimal(q.denominator)
    def sine(x):
        term = x
        total = x
        for n in range(1, 80):
            term *= -x*x/(Decimal(2*n)*Decimal(2*n+1))
            total += term
        return total
    with localcontext() as ctx:
        ctx.prec = 100
        assert decimal(lo)-sine(decimal(lo))/10-1 <= Decimal('1e-80')
        assert decimal(hi)-sine(decimal(hi))/10-1 >= -Decimal('1e-80')
    assert hi-lo < Q(1, 1000)


def test_rest_double_pendulum_and_exact_inelastic_energy_accounting():
    assert example(5)['value'] == [[0,0],[0,0]]
    assert example(6)['value'] == [0,1]
    request = {**ENTRIES[6]['example'], 'restitution': 0}
    inelastic = run(6, request)
    assert inelastic['value'] == [Q(1,2), Q(1,2)]
    assert inelastic['heat_generated'] == Q(1,4)
    assert example(9)['value'] == Q(1,2) and example(9)['entropy_production'] == 0
    with pytest.raises(ExecutionFailure):
        run(9, {**ENTRIES[9]['example'], 'work': 51})


def test_maxwell_grid_normalisation_ising_and_magnetic_divergence():
    distribution = example(10)
    assert sum(distribution['value']) == 1
    for chosen, (lo,hi) in zip(distribution['value'], distribution['probability_enclosures']):
        assert lo <= chosen <= hi
    assert example(11)['configurations'] == 16
    request = deepcopy(ENTRIES[12]['example'])
    request['magnetic_x'] = [[1,2],[3,4]]
    request['magnetic_y'] = [[-1,3],[5,2]]
    result = run(12, request)
    def divergence(bx,by,i,j):
        return bx[(i+1)%2][j]-bx[i][j]+by[i][(j+1)%2]-by[i][j]
    for i in range(2):
        for j in range(2):
            assert divergence(result['magnetic_x'],result['magnetic_y'],i,j) == divergence(request['magnetic_x'],request['magnetic_y'],i,j)
    assert example(13)['residual_infinity_norm'] == 0


def test_quantum_truncation_and_pauli_state_have_explicit_correct_invariants():
    oscillator = example(18)
    assert oscillator['value'] == [Q(1,2),Q(3,2),Q(5,2)]
    assert oscillator['commutator'] == [[1,0,0],[0,1,0],[0,0,-2]]
    spin = example(19)
    assert spin['value'] == [0,0,1] and spin['bloch_length_squared'] == 1
    with localcontext() as context:
        context.prec=80
        def atan_decimal(x):
            term=x
            total=x
            for k in range(1,100):
                term *= -x*x
                total += term/Decimal(2*k+1)
            return total
        pi=16*atan_decimal(Decimal(1)/5)-4*atan_decimal(Decimal(1)/239)
        energy=pi*pi/2
        lo,hi=example(17)['value']
        assert Decimal(lo.numerator)/lo.denominator <= energy <= Decimal(hi.numerator)/hi.denominator
    assert example(22)['H_squared'] == 1


def test_atom_balance_limiting_reagent_and_hess_witnesses():
    assert example(23)['value'] == [2,1,2]
    limiting = example(24)
    assert limiting['value'] == Q(3,2)
    assert limiting['remaining'] == [0,Q(1,2)]
    assert limiting['product_amounts'] == [3]
    assert example(25)['value'] == [1,2,1,0,2]
    assert example(26)['value'] == -30
    with pytest.raises(ExecutionFailure):
        run(23, {'conservation_matrix': [[1,1]]})
    with pytest.raises(ExecutionFailure):
        run(26, {**ENTRIES[26]['example'], 'target': [9,0,-1]})


def test_chemical_equilibria_and_rate_laws():
    assert example(27)['value'] == [[Q(1,2),Q(1,2)],[Q(1,2),Q(1,2)]]
    assert example(28)['direction'] == 'equilibrium'
    lower, upper = example(29)['value']
    assert 0 < lower <= upper < Q(1,10)
    ka = Q(1,10000)
    kw = Q(1,10**14)
    total = Q(1,10)
    def balance(h):
        return h-kw/h-total*ka/(h+ka)
    assert balance(lower) <= 0 <= balance(upper)
    assert example(30)['value'] == [Q(2,3),Q(2,3)]
    assert example(31)['value'] == 2
    assert example(33)['value'] == [1,1]
    assert example(34)['value'] == Q(3,10)
    assert example(35)['value'] == [0,0]
    assert example(36)['value'] == 2
    assert example(38)['allowed'] == 1


def affine_oracle(a,b,match=2,mismatch=-1,opening=2,extension=1):
    @lru_cache(None)
    def best(i,j,last):
        if i==len(a) and j==len(b):
            return Q(0)
        choices=[]
        if i<len(a) and j<len(b):
            choices.append((match if a[i]==b[j] else mismatch)+best(i+1,j+1,0))
        if i<len(a):
            choices.append(-(extension if last==1 else opening)+best(i+1,j,1))
        if j<len(b):
            choices.append(-(extension if last==2 else opening)+best(i,j+1,2))
        return max(choices)
    return best(0,0,0)


@pytest.mark.parametrize('a,b', [('', ''), ('A',''), ('AC','ATTC'), ('GAT','GCT')])
def test_affine_global_alignment_against_exhaustive_path_oracle(a,b):
    result = run(39, {**ENTRIES[39]['example'], 'sequence1': a, 'sequence2': b})
    assert result['value'] == affine_oracle(a,b)
    left,right = result['alignment']
    assert left.replace('-','') == a and right.replace('-','') == b
    assert len(left)==len(right)


def test_local_alignment_fm_index_eulerian_spelling_and_fitch():
    assert example(40)['value'] == 6
    assert example(41)['value'] == [0,3]
    assembly = example(42)
    sequence = assembly['value']
    assert Counter(sequence[i:i+3] for i in range(len(sequence)-2)) == Counter(ENTRIES[42]['example']['kmers'])
    assert assembly['unique_original_reconstruction'] == 0
    assert example(46)['score'] == 1
    assert run(47, {'difference_fraction':0})['value'] == [0,0]
    with pytest.raises(ExecutionFailure):
        run(47, {'difference_fraction':Q(3,4)})


def test_ecology_population_bounds_alleles_molecular_force_and_membrane_mass():
    assert example(48)['value'] == [[1,1],[1,1],[1,1]]
    assert all(0<=x<=10 for x in example(49)['trace'])
    assert example(50)['value'] == [Q(1,9),Q(4,9),Q(4,9)]
    assert example(51)['value'] == 0 and example(51)['force'] == [24,0,0]
    assert example(53)['value'] == [Q(9,5),Q(1,5)]
    assert example(53)['total_amount'] == 2


@pytest.mark.parametrize('n', [0,1,2,3,4,341,561,1105,2**64-1,18446744073709551557])
def test_deterministic_miller_rabin_known_pseudoprimes_and_boundaries(n):
    if n < 2000:
        expected = n>=2 and all(n%d for d in range(2,int(n**.5)+1))
    else:
        expected = n==18446744073709551557
    assert bool(run(54, {'n':n})['prime']) is expected


def test_factorization_bezout_and_elliptic_group_known_values():
    assert sorted(example(55)['factors']) == [83,97]
    assert example(56)['value'] == [80,10]
    assert example(57)['inverse'] == 4
    with pytest.raises(ExecutionFailure):
        run(57, {'a':6,'modulus':9})
    assert example(58)['matrix'] == [[1,0,1],[0,1,2]]


def leibniz(a):
    total = 0
    for perm in permutations(range(len(a))):
        inversions = sum(perm[i]>perm[j] for i in range(len(a)) for j in range(i+1,len(a)))
        product = 1
        for i,j in enumerate(perm):
            product *= a[i][j]
        total += (-1)**inversions*product
    return total


@pytest.mark.parametrize('matrix', [[[0,1],[2,3]], [[2,1,3],[4,1,2],[1,5,1]], [[1,2],[2,4]]])
def test_bareiss_pivoting_and_exact_divisions_against_independent_determinant(matrix):
    result = run(59, {'matrix':matrix})
    assert result['value'] == leibniz(matrix)
    for numerator,denominator,quotient in result.get('divisions',[]):
        assert numerator == denominator*quotient and quotient.denominator == 1


def test_orthogonal_factorisation_eigenvalue_enclosures_quadrature_and_roots():
    gs = example(60)
    q = gs['value']
    columns = list(zip(*q))
    assert sum(a*b for a,b in zip(*columns)) == 0
    assert gs['unit_normalized'] == 0
    for interval, true_root in zip(example(61)['value'], [1,3]):
        assert interval[0] <= true_root <= interval[1]
        assert interval[1]-interval[0] <= Q(1,2**20)
    lo,hi = example(62)['interval']
    assert lo <= Q(1,5) <= hi
    lo,hi = example(63)['value']
    assert lo*lo <= 2 <= hi*hi
    assert example(64)['value'] == example(64)['exact_derivative'] == 12


def area(poly):
    return abs(sum(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[i][1]*poly[(i+1)%len(poly)][0] for i in range(len(poly))))/2


def test_convex_hull_delaunay_and_bounded_voronoi_area():
    assert example(65)['value'] == [[0,0],[1,0],[1,1],[0,1]]
    points = ENTRIES[66]['example']['points']
    triangles = example(66)['value']
    assert len(triangles)==2
    assert sum(area([points[int(i)] for i in triangle]) for triangle in triangles)==1
    cells=example(67)['value']
    assert sum(area(poly) for poly in cells)==8
    assert all(p[0]<=1 for p in cells[0]) and all(p[0]>=1 for p in cells[1])


def test_engineering_norm_covariance_kinematics_and_boundary_conditions():
    quaternion=example(70)['value']
    assert sum(x*x for x in quaternion)==1
    kalman=example(71)
    assert kalman['value']==[1] and kalman['covariance']==[[Q(1,2)]]
    with pytest.raises(ExecutionFailure):
        run(71,{**ENTRIES[71]['example'],'measurement_noise':[[0]]})
    transform=example(72)['value']
    assert [transform[i][3] for i in range(3)]==[1,1,0]
    assert example(73)['value'][0]==[[1,1],[0,0],[1,1],[0,0]]
    assert example(74)['coefficients']==[0,0,0,10,-15,6]
    assert example(74)['value']==[Q(1,2),Q(15,8),0]


def test_powerflow_local_conditions_fault_current_truss_and_loads():
    flow=example(75)
    assert flow['local_contraction_conditions']==1
    assert abs(flow['value'][0]-Q(9,10))<=flow['radius']
    eta=flow['newton_correction_bound'];bound=flow['jacobian_lipschitz_bound'];radius=flow['radius']
    assert bound*radius<1 and eta+bound*radius*radius/2<=radius
    assert example(76)['value']==[5,-5]
    assert example(78)['value']==[0,0,-1,0,1,0]
    assert example(79)['value']==[32000,32000]
    assert example(80)['value']==90000
    assert example(80)['base_overturning_moment']==90000


def test_hypothesis_generator_route_and_multiphysics_exact_conservation():
    assert example(99)['value']==[1,2]
    assert example(99)['held_out_errors']==[0]
    assert example(100)['value']==[0,1] and example(100)['objective_cost']==3
    assert example(101)['Lean_axioms_added']==0
    assert example(101)['citation_existence_verified']==0
    coupled=example(102)
    assert coupled['total_energy_before']==coupled['total_energy_after']
    assert coupled['value'][4]+coupled['value'][5]==1


def test_units_convert_scales_and_reject_incompatible_addition():
    nodes=[{'operation':'value','unit':'m','value':1}, {'operation':'value','unit':'cm','value':1}, {'operation':'add','left':0,'right':1}]
    result=run(103,{'nodes':nodes})['value']
    assert result[-1]['value']==Q(101,100) and result[-1]['dimensions']==[0,1,0,0,0,0,0]
    nodes[1]['unit']='s'
    with pytest.raises(ExecutionFailure):run(103,{'nodes':nodes})


def test_falsification_singularities_and_seeded_noise_do_not_invent_proofs():
    assert example(105)['value']==[[0,-1]] and example(105)['universal_claim_proved']==0
    assert example(106)['value']==[0] and example(106)['interval_excludes_zero']==0
    assert example(107)==run(107,ENTRIES[107]['example'])
    assert sum(example(107)['normalised_weights'])==1


def test_executable_article_svg_and_anchor_requests_keep_provenance_and_authority_separate():
    paper=example(108)
    for name,text in paper['artifacts'].items():
        assert paper['sha256'][name]==hashlib.sha256(text.encode()).hexdigest()
    assert paper['manifest_sha256']==hashlib.sha256(canonical(paper['sha256']).encode()).hexdigest()
    assert paper['formal_admission']==0 and paper['external_publication']==0
    svg=example(109)
    assert '<title>Exact &lt;data&gt;</title>' in svg['value']
    assert '0.333333' in svg['value'] and svg['display_quantum']==Q(1,10**6)
    anchor=example(110)
    assert anchor['bitcoin_op_return_script_hex']=='6a20'+'0'*64
    assert anchor['broadcast']==0 and anchor['immutable_timestamp_verified']==0


def test_tensor_connection_csv_complex_kdtree_and_sparse_quantum():
    assert example(112)['value']==[2,0]
    metric=[[1,0],[0,4]]
    derivative=[[[0,0],[0,4]],[[0,0],[0,0]]]
    gamma=run(111,{'metric':metric,'metric_derivative':derivative})['value']
    assert gamma[0][1][1]==-2 and gamma[1][0][1]==Q(1,2)
    assert example(113)['value']==[[1,2],[3,4]]
    csv=run(113,{'text':'a,b\r\n"x,y","line1\nline2"\r\n','header':1})
    assert csv['value']==[['x,y','line1\nline2']]
    assert example(114)['value']==[2,Q(1,100)]
    assert example(115)['value']==[[2**31,[1,0]]]
    result=run(115,{'qubits':2,'state':[[0,[1,0]]],'gates':[{'operation':'R','target':0,'a':Q(3,5),'b':Q(4,5)},{'operation':'CNOT','control':0,'target':1}]})
    assert result['value']==[[0,[Q(3,5),0]],[3,[Q(4,5),0]]]
    with pytest.raises(ExecutionFailure):
        run(115,{'qubits':1,'state':[[0,[1,0]]],'gates':[{'operation':'H','target':0}]})


@pytest.mark.parametrize('identifier,payload',[
    (1,{'position':0,'momentum':0,'mass':0,'spring':1,'step':1}),
    (14,{'index1':1,'index2':0,'incident_sine':0}),
    (23,{'conservation_matrix':[[1,0,0]]}),
    (36,{'h':0,'k':0,'l':0,'a':1,'lattice':'cubic'}),
    (54,{'n':2**64}),
    (63,{'coefficients':[1,0,1],'lower':-1,'upper':1}),
    (66,{'points':[[0,0],[1,0],[2,0]]}),
    (73,{'robot_model':'arbitrary-6R','x':0,'y':0,'length1':1,'length2':1}),
    (103,{'nodes':[{'operation':'divide','left':0,'right':0}]}),
    (113,{'text':'a,b\n"unclosed'}),
    (115,{'qubits':33,'state':[[0,[1,0]]],'gates':[]}),
])
def test_invalid_scientific_domains_fail_closed(identifier,payload):
    with pytest.raises(ExecutionFailure):run(identifier,payload)


@pytest.mark.parametrize('value',[True,None,0.1,{'x':[0.1]},2**8193])
def test_host_rejects_approximate_and_unsupported_input_types(value):
    with pytest.raises(ValueError):_plain(value)


def test_host_data_budgets_apply_before_materialising_aliased_trees():
    value=['x'*1024]*5000
    with pytest.raises(ValueError,match='byte budget'):_plain(value)
    cyclic=[];cyclic.append(cyclic)
    with pytest.raises(ValueError,match='nesting'):_plain(cyclic)


def test_kalman_accepts_correlated_psd_process_noise_and_rejects_indefinite_noise():
    request={'transition':[[1,0],[0,1]],'observation':[[1,0],[0,1]],
             'covariance':[[1,0],[0,1]],'process_noise':[[1,Q(1,2)],[Q(1,2),1]],
             'measurement_noise':[[1,0],[0,1]],'state':[0,0],'measurement':[0,0]}
    result=run(71,request)
    assert result['covariance']==[[Q(23,35),Q(2,35)],[Q(2,35),Q(23,35)]]
    with pytest.raises(ExecutionFailure):
        run(71,{**request,'process_noise':[[0,1],[1,0]]})
