"""Independent numerical oracles, falsification cases and resource boundaries."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from functools import lru_cache
from itertools import combinations, product
import hashlib
import random

import pytest
from omega_engines import catalog, run
from omega_platform.sandbox import ExecutionFailure

ENTRIES = {e['id']:e for e in catalog()['engines']}


def request(identifier): return deepcopy(ENTRIES[identifier]['example'])
@lru_cache(None)
def example(identifier): return run(identifier, request(identifier))
def decimal(q):
    q=Q(q); return Decimal(q.numerator)/Decimal(q.denominator)
def polynomial(terms, point):
    total=Q(0)
    for coefficient, exponents in terms:
        term=Q(coefficient)
        for x,e in zip(point,exponents): term*=Q(x)**int(e)
        total+=term
    return total


@pytest.mark.parametrize('identifier',range(1,17))
def test_each_of_the_sixteen_native_implementations_executes(identifier):
    result=example(identifier)
    assert type(result) is dict and result['formal_admission']==0


@pytest.mark.parametrize('bits',[8,24,64])
@pytest.mark.parametrize('op,center,radius',[('exp',Q(1,3),Q(1,5)),('sin',Q(-1,2),Q(1,4)),('log',Q(1),Q(1,4))])
def test_taylor_remainder_contains_independent_high_precision_values(bits,op,center,radius):
    result=run(1,dict(center=center,radius=radius,order=6,bits=bits,expression=[op,['var']]))
    def sine(x):
        total=x; term=x
        for k in range(1,70):
            term*=-x*x/(Decimal(2*k)*Decimal(2*k+1)); total+=term
        return total
    with localcontext() as ctx:
        ctx.prec=90
        for i in range(17):
            z=-radius+2*radius*Q(i,16); x=decimal(center+z)
            actual=x.exp() if op=='exp' else x.ln() if op=='log' else sine(x)
            approximation=sum((c*z**k for k,c in enumerate(result['coefficients'])),Q(0))
            lo,hi=result['remainder']
            assert decimal(approximation+lo)<=actual<=decimal(approximation+hi)
            assert decimal(result['range'][0])<=actual<=decimal(result['range'][1])


def test_taylor_composition_and_quantized_polynomial_product():
    ast=['mul',['add',['var'],['const','1/3']],['add',['var'],['const','-2/7']]]
    result=run(1,dict(center='1/9',radius='1/3',order=1,bits=8,expression=ast))
    for i in range(-8,9):
        z=Q(i,24); x=Q(1,9)+z; actual=(x+Q(1,3))*(x-Q(2,7))
        approximation=sum((c*z**k for k,c in enumerate(result['coefficients'])),Q(0))
        assert approximation+result['remainder'][0]<=actual<=approximation+result['remainder'][1]
    with pytest.raises(ExecutionFailure):run(1,dict(center=0,radius=1,order=4,expression=['log',['var']]))
    with pytest.raises(ExecutionFailure):run(1,dict(center=0,radius=1,order=4,expression=['div',['const',1],['var']]))


def ast_value(ast,point):
    if ast[0]=='var':return point[int(ast[1])]
    if ast[0]=='const':return Q(ast[1])
    a,b=ast_value(ast[1],point),ast_value(ast[2],point)
    return a+b if ast[0]=='add' else a*b


@pytest.mark.parametrize('ast',[
    ['mul',['add',['var',0],['const',1]],['add',['var',0],['const',-1]]],
    ['add',['mul',['const','2/3'],['var',0]],['mul',['const','-2/3'],['var',0]]],
    ['mul',['const',0],['add',['var',0],['var',1]]],
])
def test_egraph_rewrites_preserve_ring_semantics_and_extraction_is_finite(ast):
    result=run(2,dict(variables=2,expression=ast,max_nodes=96,rounds=8))
    for x,y in product([Q(-3,2),Q(0),Q(7,5)],repeat=2):
        assert ast_value(result['value'],[x,y])==ast_value(ast,[x,y])
    assert result['polynomial_equivalence_checked']==1 and result['global_optimum_claimed']==0
    limited=run(2,dict(variables=2,expression=ast,max_nodes=16,rounds=1))
    assert limited['budget_limited'] in (0,1)
    assert ast_value(limited['value'],[Q(2),Q(3)])==ast_value(ast,[Q(2),Q(3)])
    with pytest.raises(ExecutionFailure):run(2,dict(variables=1,expression=['div',['var',0],['var',0]]))


def vertex_optimum(matrix,b,c):
    constraints=[*zip(matrix,b),([-1,0],0),([0,-1],0)]; vertices=[]
    for (a,x),(d,y) in combinations(constraints,2):
        determinant=Q(a[0])*d[1]-Q(a[1])*d[0]
        if determinant:
            point=[(Q(x)*d[1]-Q(a[1])*y)/determinant,(Q(a[0])*y-Q(x)*d[0])/determinant]
            if all(sum(Q(v)*w for v,w in zip(row,point))<=bound for row,bound in constraints):vertices.append(point)
    return max((sum(Q(v)*w for v,w in zip(c,p)) for p in vertices),default=None)


@pytest.mark.parametrize('seed',range(24))
def test_rational_simplex_against_exhaustive_exact_vertex_oracle(seed):
    rng=random.Random(seed)
    matrix=[[1,0],[0,1],*[ [rng.randint(-3,3),rng.randint(-3,3)] for _ in range(4)]]
    b=[3,4,*[Q(rng.randint(-4,12),rng.randint(1,3)) for _ in range(4)]];c=[rng.randint(-4,4),rng.randint(-4,4)]
    oracle=vertex_optimum(matrix,b,c); result=run(3,dict(A=matrix,b=b,c=c))
    if oracle is None:
        assert result['status']=='infeasible'
        y=result['farkas'];assert all(v>=0 for v in y)
        assert sum(y[i]*b[i] for i in range(len(b)))<0
    else:
        assert result['status']=='optimal' and result['objective']==oracle
        x=result['value'];y=result['dual']
        assert all(v>=0 for v in x+y)
        assert all(sum(a*z for a,z in zip(row,x))<=bound for row,bound in zip(matrix,b))
        assert sum(yi*bi for yi,bi in zip(y,b))==oracle


def test_simplex_unbounded_farkas_degeneracy_and_bland_anti_cycling():
    unbounded=run(3,dict(A=[[-1]],b=[-1],c=[1]))
    assert unbounded['status']=='unbounded' and unbounded['value'][0]>=1 and unbounded['ray'][0]>0
    assert run(3,dict(A=[[1]],b=[-1],c=[1]))['status']=='infeasible'
    assert run(3,dict(A=[[0,0],[1,0],[0,1]],b=[0,1,1],c=[1,1]))['objective']==2
    beale=run(3,dict(A=[['1/2','-11/2','-5/2',9],['1/2','-3/2','-1/2',1],[1,0,0,0]],b=[0,0,1],c=[10,-57,-9,-24],max_pivots=100))
    assert beale['objective']==1 and beale['pivots']<100
    with pytest.raises(ExecutionFailure):run(3,{**request(3),'max_pivots':1})


def test_sindy_recovers_sparse_equation_and_tests_unseen_points():
    result=example(4)
    assert result['value']==[1,2,0] and result['support']==[0,1]
    assert result['training_squared_error']==result['holdout_squared_error']==0
    assert result['empirical_law_proven']==0 and polynomial(result['polynomial'],[Q(101,3)])==Q(205,3)
    invalid={**request(4),'exponents':[[0],[0]]}
    with pytest.raises(ExecutionFailure):run(4,invalid)
    singular={**request(4),'samples':[[0],[0],[0],[0]],'derivatives':[1,1,1,1]}
    with pytest.raises(ExecutionFailure):run(4,singular)


def test_variational_derivation_rotation_symmetry_and_time_dependent_lagrangian():
    lagrangian=[[1,[0,0,2,0,0]],[1,[0,0,0,2,0]],['-3/2',[2,0,0,0,0]],['-3/2',[0,2,0,0,0]]]
    result=run(5,dict(coordinates=2,lagrangian=lagrangian))
    point=[1,2,3,4,0,5,6]
    assert [polynomial(p,point) for p in result['value']]==[13,18]
    assert result['time_translation_invariant']==1 and result['rotation_symmetries'][0]['invariant']==1
    assert result['noether_identity_residual']==[]
    timed=run(5,dict(coordinates=1,lagrangian=[['1/2',[0,2,0]],[1,[1,0,1]]]))
    assert polynomial(timed['value'][0],[2,3,5,7])==2 and timed['time_translation_invariant']==0


def test_variational_simulation_del_symplecticity_reversibility_and_energy_drift():
    forward=example(6)
    assert forward['physical_energy_drift']!=0 and all(all(v==0 for v in row) for row in forward['DEL_residuals'])
    reverse=run(6,{**request(6),'position':forward['position'],'momentum':[-p for p in forward['momentum']]})
    assert reverse['position']==[1] and reverse['momentum']==[0]
    jac=forward['jacobian_at_initial_state']; assert jac[0][0]*jac[1][1]-jac[0][1]*jac[1][0]==1
    quartic=run(6,{**request(6),'potential':[['1/4',[4]]],'steps':3})
    assert quartic['physical_energy_drift']!=0 and quartic['symplectic_identity_checked']==1


def test_discrete_exterior_calculus_on_tetrahedron_has_boundary_squared_zero():
    result=run(6,dict(mode='dec',vertices=4,simplices=[[0,1,2,3]],degree=0,form=[2,5,7,11]))
    assert [len(c) for c in result['cells']]==[4,6,4,1]
    matrices=result['value']
    for left,right in zip(matrices,matrices[1:]):
        assert all(sum(x*y for x,y in zip(row,column))==0 for row in left for column in zip(*right))
    assert result['second_exterior_derivative']==[0]*4
    with pytest.raises(ExecutionFailure):run(6,dict(mode='dec',vertices=3,simplices=[[2,1,0]]))


def test_schur_elimination_and_coarse_variance_decomposition():
    gaussian=example(7)
    assert gaussian['value']==[[Q(7,2)]] and gaussian['linear']==[-1] and gaussian['constant']==-1
    assert gaussian['fast_state']==[Q(-5,2)] and gaussian['original_energy']==gaussian['effective_energy']==Q(47,4)
    coarse=run(7,dict(mode='coarse',values=[1,3,5],weights=[1,2,1],groups=[0,0,1],bins=2))
    assert coarse['value']==[Q(7,3),5] and coarse['unresolved_variance']==Q(8,3)
    assert coarse['fine_quadratic_moment']==coarse['coarse_quadratic_moment']+coarse['unresolved_variance']
    with pytest.raises(ExecutionFailure):run(7,{**request(7),'hessian':[[1,1],[1,1]]})


@pytest.mark.parametrize('rank',[1,2])
def test_tensor_train_residual_and_norm_against_full_independent_reconstruction(rank):
    values=[Q(x,3) for x in [1,2,-1,4,3,7,6,-2]]
    result=run(8,dict(mode='compress',dimensions=[2,2,2],values=values,max_rank=rank))
    reconstructed=result['dense_reconstruction']
    assert result['squared_Frobenius_error']==sum((a-b)**2 for a,b in zip(values,reconstructed))
    assert result['squared_norm']==sum(v*v for v in reconstructed)
    assert (result['squared_Frobenius_error']==0)==(rank==2)
    assert result['SVD_optimality_claimed']==0


def test_tensor_train_long_product_state_does_not_materialize_exponential_tensor():
    result=run(8,dict(mode='contract',cores=[[[[1],[2]]]]*64,indices=[1]*64))
    assert result['value']==5**64 and result['amplitude']==2**64
    zeros=run(8,dict(mode='compress',dimensions=[2,2],values=[0]*4,max_rank=1))
    assert zeros['squared_Frobenius_error']==zeros['squared_norm']==0


def test_active_inference_bayes_sensor_provenance_and_action_constraints():
    result=example(9)
    assert result['action_proposal']==1 and result['external_action_executed']==0
    assimilated=run(9,{**request(9),'observation':1,'source':'recorded-sensor-test','sequence':2,'last_sequence':1})
    assert assimilated['belief']==[0,1] and assimilated['sensor_origin_authenticated']==0
    with localcontext() as ctx:
        ctx.prec=70
        expected=(Decimal(10)/9).ln(); lo,hi=result['cost_intervals'][1]
        assert decimal(lo)<=expected<=decimal(hi)
    with pytest.raises(ExecutionFailure):run(9,{**request(9),'allowed_actions':[0,0]})
    with pytest.raises(ExecutionFailure):run(9,{**request(9),'observation':1,'source':'sensor','sequence':1,'last_sequence':1})
    masked=run(9,{**request(9),'allowed_actions':[1,0]}); assert masked['action_proposal']==0


def test_catalytic_constructor_conserves_declared_totals_and_does_not_apply_repair():
    result=example(10)
    assert result['value']==[0,0,2,1] and result['conserved_totals']==[5] and result['quiescent']==1
    bad=request(10);bad['rules'][0]['produce']=[0,0,2,0]
    with pytest.raises(ExecutionFailure):run(10,bad)
    blueprint='reviewed component'; digest=hashlib.sha256(blueprint.encode()).hexdigest()
    repair=run(10,dict(mode='repair',blueprint=blueprint,candidate='corrupt',expected_sha256=digest))
    assert repair['repair_needed']==1 and repair['applied']==0 and repair['value']==blueprint
    with pytest.raises(ExecutionFailure):run(10,dict(mode='repair',blueprint=blueprint,candidate='corrupt',expected_sha256='0'*64))


def test_eqprop_local_contrast_matches_direct_fixed_points_with_declared_error():
    result=example(11); beta=Q(1,10); w=Q(1,4)
    free=[1/(1-w*w),w/(1-w*w)]
    determinant=1+beta-w*w; nudged=[(1+beta+w*beta/2)/determinant,(w+beta/2)/determinant]
    true_gradient=-(nudged[0]*nudged[1]-free[0]*free[1])/beta
    assert abs(result['value'][0][1]-true_gradient)<=result['relaxation_gradient_error_upper'][0][1]
    for phase,exact in [(result['free'],free),(result['nudged'],nudged)]:
        assert phase['converged']==1 and phase['final_energy']<=phase['initial_energy']
        assert max(abs(a-b) for a,b in zip(phase['state'],exact))<=phase['state_error_inf_upper']
    truncated=run(11,{**request(11),'max_iterations':1})
    assert truncated['free']['converged']==0 and truncated['update_admissible']==0
    with pytest.raises(ExecutionFailure):run(11,{**request(11),'step':2})
    with pytest.raises(ExecutionFailure):run(11,{**request(11),'weights':[[0,2],[2,0]]})


def test_hopfield_interval_retrieval_and_fifo_eviction_expose_finite_capacity():
    result=example(12)
    assert result['state']==[1,0] and result['infinite_memory_claimed']==0
    with localcontext() as ctx:
        ctx.prec=80
        scores=[decimal(2*sum(k*q for k,q in zip(key,result['query']))) for key in result['keys']]
        weights=[s.exp() for s in scores]; actual=sum(w*decimal(v[0]) for w,v in zip(weights,result['values']))/sum(weights)
        lo,hi=result['value_intervals'][0]; assert decimal(lo)<=actual<=decimal(hi)
    updated=run(12,{**request(12),'new_key':[1,1],'new_value':[30]})
    assert updated['keys']==[[0,1],[1,1]] and updated['values']==[[20],[30]] and updated['evicted']==1
    collision=run(12,{**request(12),'keys':[[1,0],[1,0]]})
    assert collision['value_intervals'][0][0]<=15<=collision['value_intervals'][0][1]


def test_structural_causal_interventions_and_counterfactuals_reuse_exogenous_world():
    base=request(13)
    observational=run(13,{**base,'interventions':[],'evidence':[[0,1]]})
    assert observational['value']==[1,0]
    assert example(13)['value']==[Q(1,2),Q(1,2)]
    counterfactual=run(13,{**base,'interventions':[],'evidence':[[0,1]],'counterfactual':[[0,0]]})
    assert counterfactual['value']==[0,1] and counterfactual['posterior_noise_worlds']==[0,1]
    with pytest.raises(ExecutionFailure):run(13,{**base,'interventions':[],'evidence':[[1,1]]})


def backdoor_request():
    return dict(mode='backdoor',nodes=[{'parents':[],'noise':0,'table':[0,1]},
        {'parents':[0],'noise':1,'table':[0,1,1,0]}, {'parents':[0,1],'table':[0,1,1,1]}],
        noise_worlds=[{'values':[a,b],'probability':Q(1,2)*(Q(1,4) if b else Q(3,4))} for a,b in product(range(2),repeat=2)],
        treatment=1,outcome=2,value=0,controls=[0])


def test_backdoor_moral_ancestral_graph_and_positivity_checked_before_adjustment():
    data=backdoor_request(); result=run(13,data)
    assert result['value']==[Q(1,2),Q(1,2)]
    with pytest.raises(ExecutionFailure):run(13,{**data,'controls':[]})
    with pytest.raises(ExecutionFailure):run(13,{**data,'controls':[2]})
    correlated={**data,'noise_worlds':[{'values':[0,0],'probability':'1/2'},{'values':[1,1],'probability':'1/2'}]}
    with pytest.raises(ExecutionFailure):run(13,correlated)


def jepa_loss(data):
    w=[list(map(Q,row)) for row in data['encoder']]; teacher=[list(map(Q,row)) for row in data['target_encoder']]
    p=[list(map(Q,row)) for row in data['predictor']]; action=[list(map(Q,row)) for row in data['action_map']]
    dot=lambda a,b:sum((x*Q(y) for x,y in zip(a,b)),Q(0))
    z=[[dot(row,x) for row in w] for x in data['context']]
    t=[[dot(row,y) for row in teacher] for y in data['target']]
    b=len(z); d=len(w); loss=Q(0)
    for state,expected,u in zip(z,t,data['actions']):
        for i in range(d): loss+=(dot(p[i],state)+dot(action[i],u)-expected[i])**2/b
    means=[sum(row[i] for row in z)/b for i in range(d)]
    cov=[[sum((row[i]-means[i])*(row[j]-means[j]) for row in z)/(b-1) for j in range(d)] for i in range(d)]
    loss+=Q(data['variance_weight'])*sum(max(0,Q(data['variance_floor'])-cov[i][i])**2 for i in range(d))
    loss+=Q(data['covariance_weight'])*sum(cov[i][j]**2 for i in range(d) for j in range(d) if i!=j)
    return loss


def test_jepa_gradient_ema_and_collapse_diagnostic_against_independent_objective():
    data=request(14); result=example(14); assert result['before']['loss']==jepa_loss(data)
    epsilon=Q(1,10**6)
    for key,gradient in [('encoder','encoder_gradient'),('predictor','predictor_gradient'),('action_map','action_gradient')]:
        for i,row in enumerate(data[key]):
            for j,_ in enumerate(row):
                plus,minus=deepcopy(data),deepcopy(data)
                plus[key][i][j]=Q(row[j])+epsilon;minus[key][i][j]=Q(row[j])-epsilon
                numerical=(jepa_loss(plus)-jepa_loss(minus))/(2*epsilon)
                assert abs(numerical-result['before'][gradient][i][j])<Q(1,10**10)
    for i,row in enumerate(result['value']):
        for j,x in enumerate(row):assert result['target_encoder'][i][j]==Q(9,10)*Q(data['target_encoder'][i][j])+x/10
    assert result['after']['prediction_loss']<result['before']['prediction_loss']
    collapsed=run(14,{**data,'encoder':[[0,0],[0,0]],'target_encoder':[[0,0],[0,0]]})
    assert collapsed['after']['collapsed']==1 and collapsed['noncollapse_guaranteed']==0


def test_hypernetwork_learns_task_to_program_map_and_emits_cases_without_ood_claim():
    data={**request(15),'mode':'fit_generate','training_features':[[1,0],[1,1],[1,2]],
          'training_coefficients':[[1,0],[1,2],[1,4]],'features':[1,3],
          'cases':[{'input':[0],'expected':1},{'input':[2],'expected':13}]}
    result=run(15,data)
    assert result['value']==[1,6] and result['training_squared_error']==0 and result['examples_passed']==1
    assert result['generalization_proven']==0 and result['compiled']==0
    invalid={**request(15),'cases':[{'input':[0],'expected':5}]}
    assert run(15,invalid)['examples_passed']==0


def test_microarena_messages_fairness_deadlock_and_resource_limits():
    result=example(16)
    assert result['value']==[[0,Q(7,3)],[1,Q(7,3)]] and result['completed']==2 and result['messages']==1
    assert result['logical_reserved_bytes']==2*65536+7*64+256
    blocked=run(16,{**request(16),'program':[{'op':'recv','register':1}]})
    assert blocked['deadlock']==1 and blocked['completed']==0
    loop=run(16,{**request(16),'program':[{'op':'jump','target':0}],'max_turns':5})
    assert loop['turn_budget_exhausted']==1 and loop['turns']==5
    with pytest.raises(ExecutionFailure):run(16,{**request(16),'memory_bytes':4096})
    with pytest.raises(ExecutionFailure):run(16,{**request(16),'program':[{'op':'set','register':1,'value':2**63}]})
    with pytest.raises(ExecutionFailure):run(16,{**request(16),'program':[{'op':'set','register':1,'value':2**63-1},{'op':'add','register':1,'value':1}]})


@pytest.mark.parametrize('identifier',range(1,17))
def test_data_boundary_rejects_floats_bools_and_excessive_alias_expansion(identifier):
    with pytest.raises(ValueError):run(identifier,{'unexpected':1.5})
    with pytest.raises(ValueError):run(identifier,{'unexpected':True})
    alias=['x']*1000
    with pytest.raises(ValueError):run(identifier,{'aliases':[alias]*100})
