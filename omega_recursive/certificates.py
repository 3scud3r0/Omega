"""Independent exact checker and statement-bound finite kernel certificates.

Kernel facts prove closed coefficient arithmetic and a declared cost inequality.
Correctness of polynomial reflection into these facts is a separate trust
boundary; no global theorem about intelligence, hardware speed or C is claimed.
"""
from fractions import Fraction

from omega_kernel.certificates import ProofBuilder
from omega_kernel.protocol import plain, sha256
from omega_kernel.runtime import request as kernel_request
from omega_security.encoding import canonical


def encoded(value):
    return canonical(plain(value),max_bytes=4*1024**2,max_nodes=100000,max_depth=48)


def read_dag(document):
    if type(document) is not dict or set(document) != {'format','variables','nodes','root'}:
        raise ValueError('DAG exact fields')
    if document['format'] != 'omega-symbolic-dag-1':
        raise ValueError('DAG version')
    variables = document['variables']
    if type(variables) is not int or not 1 <= variables <= 4:
        raise ValueError('DAG variable count')
    raw = document['nodes']
    if type(raw) is not list or not 1 <= len(raw) <= 256:
        raise ValueError('DAG node budget')
    nodes = []
    costs = []
    for index,node in enumerate(raw):
        if type(node) is not list or len(node) != 3:
            raise ValueError('DAG node shape')
        op,value,children = node
        arity = {'const':0,'var':0,'neg':1,'add':2,'sub':2,'mul':2}.get(op)
        if arity is None or type(children) is not list or len(children) != arity:
            raise ValueError('DAG operator arity')
        if any(type(c) is not int or not 0 <= c < index for c in children):
            raise ValueError('DAG edges must point strictly backwards')
        if op == 'const':
            if type(value) not in {int,str}:
                raise ValueError('Exact DAG literal required')
            value = Fraction(value)
            if max(abs(value.numerator).bit_length(),value.denominator.bit_length()) > 256:
                raise ValueError('DAG literal bit budget')
        elif op == 'var':
            if type(value) is not int or not 0 <= value < variables:
                raise ValueError('DAG variable index')
        elif type(value) is not int or value != 0:
            raise ValueError('Operator payload zero required')
        size = 1+sum(costs[c] for c in children)
        if size > 127:
            raise ValueError('Expanded DAG budget')
        costs.append(size)
        nodes.append((op,value,children))
    root = document['root']
    if type(root) is not int or not 0 <= root < len(nodes):
        raise ValueError('DAG root')
    return variables,nodes,root


def reachable(nodes,root):
    seen = set()
    todo = [root]
    while todo:
        node = todo.pop()
        if node not in seen:
            seen.add(node)
            todo.extend(nodes[node][2])
    return seen


def arithmetic_cost(document):
    _,nodes,root = read_dag(document)
    return sum(nodes[i][0] not in {'const','var'} for i in reachable(nodes,root))


def _term(builder, op, left, right=None):
    if op == 'neg':
        return builder.node('rat-neg',left)
    if op == 'sub':
        return builder.node('rat-add',left,builder.node('rat-neg',right))
    return builder.node('rat-add' if op == 'add' else 'rat-mul',left,right)


def claim_packet(claim):
    if type(claim) is not dict or set(claim) != {'format','dag','observations'} or claim['format'] != 'omega-epistemic-claim-1':
        raise ValueError('Claim exact fields/version')
    variables,nodes,root = read_dag(claim['dag'])
    observed = claim['observations']
    if type(observed) is not list or not 1 <= len(observed) <= 16:
        raise ValueError('Proof certificate observations 1..16')
    builder = ProofBuilder()
    equations = []
    for row in observed:
        if type(row) is not list or len(row) != 2 or type(row[0]) is not list or len(row[0]) != variables:
            raise ValueError('Observation shape')
        if any(type(value) not in {int,str} for value in [*row[0],row[1]]):
            raise ValueError('Exact observations required')
        inputs = [builder.rational(value) for value in row[0]]
        terms = []
        for op,payload,children in nodes:
            if op == 'const':
                term = builder.rational(payload)
            elif op == 'var':
                term = inputs[payload]
            elif op == 'neg':
                term = _term(builder,op,terms[children[0]])
            else:
                term = _term(builder,op,terms[children[0]],terms[children[1]])
            terms.append(term)
        equations.append((terms[root],builder.rational(row[1])))
    return builder.bundle(equations)


def certify_claim(claim):
    claim = plain(claim)
    return {'format':'omega-point-certificate-1','claim':claim,'packet':claim_packet(claim),
            'scope':'exact polynomial outputs at the supplied observations only'}


def verify_claim(certificate):
    if type(certificate) is not dict or set(certificate) != {'format','claim','packet','scope'}:
        raise ValueError('Point certificate exact fields')
    expected = certify_claim(certificate['claim'])
    if encoded(expected) != encoded(certificate):
        raise ValueError('Proof is not bound to this exact claim')
    outcome = kernel_request('verify',expected['packet'])
    return {'accepted':outcome['accepted'],'verified':outcome['verified'],
            'claim_sha256':sha256(encoded(expected['claim'])),
            'certificate_sha256':sha256(encoded(expected)),'scope':expected['scope'],'kernel':outcome}


def polynomial_trace(document,builder):
    variables,nodes,root = read_dag(document)
    zero_exp = (0,)*variables
    zero = builder.rational(0)
    one = builder.rational(1)
    polys = []
    for op,payload,children in nodes:
        if op == 'const':
            out = {zero_exp:builder.rational(payload)}
        elif op == 'var':
            exponent = [0]*variables
            exponent[payload] = 1
            out = {tuple(exponent):one}
        elif op == 'neg':
            out = {e:_term(builder,'neg',t) for e,t in polys[children[0]].items()}
        elif op in {'add','sub'}:
            a,b = (polys[c] for c in children)
            out = {e:_term(builder,op,a.get(e,zero),b.get(e,zero)) for e in sorted(a.keys()|b.keys())}
        else:
            a,b = (polys[c] for c in children)
            out = {}
            for e,left in sorted(a.items()):
                for f,right in sorted(b.items()):
                    exponent = tuple(x+y for x,y in zip(e,f))
                    if sum(exponent) > 12:
                        raise ValueError('Polynomial reflection degree budget 12')
                    term = _term(builder,'mul',left,right)
                    out[exponent] = _term(builder,'add',out.get(exponent,zero),term)
        if len(out) > 128:
            raise ValueError('Polynomial reflection term budget 128')
        polys.append(out)
    return polys[root]


def improvement_certificate(baseline,candidate):
    if read_dag(baseline)[0] != read_dag(candidate)[0]:
        raise ValueError('Rewrite variable domain mismatch')
    old_cost,new_cost = arithmetic_cost(baseline),arithmetic_cost(candidate)
    if new_cost >= old_cost:
        raise ValueError('No strict decrease in the declared arithmetic-node cost')
    builder = ProofBuilder()
    a = polynomial_trace(baseline,builder)
    b = polynomial_trace(candidate,builder)
    zero = builder.rational(0)
    packet = builder.bundle([(a.get(e,zero),b.get(e,zero)) for e in sorted(a.keys()|b.keys())])
    natural = builder.node('nat')
    before = builder.node('nat-literal',data=(old_cost,))
    after = builder.node('nat-literal',data=(new_cost,))
    positive = builder.node('successor',builder.node('nat-literal',data=(old_cost-new_cost-1,)))
    sum_term = builder.node('nat-add',after,positive)
    equality = builder.node('equality',natural,sum_term,before)
    proof = builder.node('refl',natural,sum_term)
    product = builder.node('sigma',equality,packet['expected'])
    pair = builder.node('pair',product,proof,packet['proof'])
    return {'format':'omega-rewrite-certificate-1','baseline':plain(baseline),'candidate':plain(candidate),
            'cost_model':'unique arithmetic DAG nodes','baseline_cost':old_cost,'candidate_cost':new_cost,
            'packet':builder.packet(pair,product),
            'scope':'closed coefficient equality facts and strict declared node-cost decrease; reflection is trusted'}


def verify_improvement(certificate):
    if type(certificate) is not dict or set(certificate) != {'format','baseline','candidate','cost_model','baseline_cost','candidate_cost','packet','scope'}:
        raise ValueError('Rewrite certificate exact fields')
    expected = improvement_certificate(certificate['baseline'],certificate['candidate'])
    if encoded(certificate) != encoded(expected):
        raise ValueError('Rewrite certificate/statement mismatch')
    outcome = kernel_request('verify',expected['packet'])
    return {'accepted':outcome['accepted'],'kernel_facts_verified':outcome['verified'],
            'certificate_sha256':sha256(encoded(expected)),'kernel':outcome,
            'formal_refinement_proved':False,'intelligence_gain_proved':False,
            'automatic_stable_promotion':False,'scope':expected['scope']}
