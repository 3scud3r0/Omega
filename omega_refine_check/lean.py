"""Trusted VC rendering from the small rational refinement AST."""
from fractions import Fraction as Q
from omega.certified_proof import check
from .syntax import rational,tree,substitute


def literal(value):
    q=rational(value);return f'(({q.numerator} : ℚ) / {q.denominator})'


def expression(node,names):
    op=node[0]
    if op=='const':return literal(node[1])
    if op=='var':
        if node[1] not in names:raise ValueError('Unbound proof variable')
        return names[node[1]]
    if op=='vector':return [expression(x,names) for x in node[1]]
    if op=='denom':return f'(({expression(node[1],names)}).den : ℚ)'
    if op=='neg':return f'(-{expression(node[1],names)})'
    if op=='relu':return f'(max 0 {expression(node[1],names)})'
    if op=='soma':
        values=expression(node[1],names)
        if not isinstance(values,list):raise ValueError('Sum requires a tensor')
        return '('+' + '.join(values)+')'
    if op=='dot':
        a,b=expression(node[1],names),expression(node[2],names)
        if not isinstance(a,list) or not isinstance(b,list) or len(a)!=len(b):raise ValueError('Dot shape mismatch')
        return '('+' + '.join(f'({x}*{y})' for x,y in zip(a,b))+')'
    if op=='pow':
        if node[2][0]!='const' or Q(node[2][1]).denominator!=1 or not 0<=Q(node[2][1])<=20:raise ValueError('Static exponent in [0,20] required')
        return f'({expression(node[1],names)} ^ {int(Q(node[2][1]))})'
    if op in ('+','-','*','/'):
        a,b=expression(node[1],names),expression(node[2],names)
        if isinstance(a,list) or isinstance(b,list):raise ValueError('Use explicit static tensor coordinates')
        return f'({a} {op} {b})'
    raise ValueError('Unknown arithmetic proof node')


def predicate(node,names):
    op=node[0]
    if op in ('true','false'):return op.capitalize()
    if op=='not':return '(¬ '+predicate(node[1],names)+')'
    if op in ('and','or'):return '('+predicate(node[1],names)+(' ∧ ' if op=='and' else ' ∨ ')+predicate(node[2],names)+')'
    if op not in ('==','!=','<=','>=','<','>'):raise ValueError('Boolean predicate required')
    if node[1][0]=='norm':
        if op not in ('<=','<') or node[2][0]!='const' or Q(node[2][1])<0:raise ValueError('Norm requires a nonnegative constant upper bound')
        values=expression(node[1][1],names)
        if not isinstance(values,list):values=[values]
        left='('+' + '.join(f'({x})^2' for x in values)+')'
        right=f'({literal(node[2][1])})^2'
    else:left,right=expression(node[1],names),expression(node[2],names)
    if isinstance(left,list) or isinstance(right,list):raise ValueError('Tensor predicates need norm or explicit coordinates')
    return '('+left+' '+{'==':'=','!=':'≠','<=':'≤','>=':'≥','<':'<','>':'>'}[op]+' '+right+')'


def divisions(node):
    if node[0]=='/':yield node[2]
    children=node[1] if node[0]=='vector' else node[1:]
    for child in children:
        if isinstance(child,(list,tuple)):yield from divisions(child)


def source(variables,assumptions,obligations,*,namespace='OmegaRefinement'):
    def split(goal):
        if goal[0]=='and':return split(goal[1])+split(goal[2])
        return [goal]
    expanded=[]
    for obligation in obligations:
        if type(obligation) is dict:expanded.extend({**obligation,'goal':g} for g in split(obligation['goal']))
        else:expanded.extend(split(obligation))
    obligations=expanded
    names={name:f'v{i}' for i,name in enumerate(variables)}
    args=' '.join(f'({lean} : ℚ)' for lean in names.values())
    hypotheses=' '.join(f'(h{i} : {predicate(p,names)})' for i,p in enumerate(assumptions))
    lines=['import Omega.Refinement',f'namespace {namespace}','set_option maxRecDepth 10000','set_option maxHeartbeats 4000000','set_option linter.unusedVariables false']
    declarations=[]
    for i,obligation in enumerate(obligations):
        if type(obligation) is dict:
            local={name:f'v{j}' for j,name in enumerate(obligation['variables'])}
            local_args=' '.join(f'({value} : ℚ)' for value in local.values())
            local_h=' '.join(f'(h{j} : {predicate(p,local)})' for j,p in enumerate(obligation['assumptions']))
            goal=predicate(obligation['goal'],local)
        else:local_args,local_h,goal=args,hypotheses,predicate(obligation,names)
        raw=obligation['goal'] if type(obligation) is dict else obligation
        proof='  omega_refine'
        if raw[0]=='!=' and raw[1][0]=='denom' and raw[2]==('const','0'):
            local_names=local if type(obligation) is dict else names
            proof=f'  simp only [div_one]\n  exact_mod_cast (Rat.den_nz {expression(raw[1][1],local_names)})'
        lines += [f'theorem obligation_{i} {local_args} {local_h} : {goal} := by',proof,f'#print axioms obligation_{i}']
        declarations.append(f'{namespace}.obligation_{i}')
    if not declarations:raise ValueError('At least one proof obligation required')
    lines.append(f'end {namespace}')
    return '\n'.join(lines)+'\n',declarations


def prove(variables,assumptions,obligations):
    generated,names=source(variables,assumptions,obligations)
    return {'source':generated,'admission':check(generated,names),'obligations':len(names)}
