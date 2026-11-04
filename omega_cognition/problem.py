"""Closed schema for arithmetic hypotheses; text never supplies host authority."""
from fractions import Fraction
from .statistics import probability
from omega_refine_check.syntax import parse,tree,identifier,rational,render


def flat(node,names):
    result=[]
    def visit(n):
        op=n[0]
        if op=='const':record=[0,-1,-1,str(rational(n[1]))]
        elif op=='var':
            if n[1] not in names:raise ValueError('Unknown hypothesis variable')
            record=[1,-1,-1,names.index(n[1])]
        elif op in ('+','-','*','/'):
            a=visit(n[1]);b=visit(n[2]);record=[{'+':2,'-':3,'*':4,'/':5}[op],a,b,'']
        elif op in ('neg','relu'):record=[6 if op=='neg' else 7,visit(n[1]),-1,'']
        else:raise ValueError('Unsupported hypothesis operator; extension must remain quarantined')
        result.append(record)
        if len(result)>63:raise ValueError('Hypothesis AST budget 63')
        return len(result)-1
    visit(tree(node));return result


def normalize(raw):
    fields={'format','variables','reference','training','candidates','constants','operators','extensions'}
    if type(raw) is not dict or set(raw)-fields or raw.get('format')!='omega-cognitive-problem-1':raise ValueError('Cognitive problem schema')
    variables=raw.get('variables')
    if type(variables) is not dict or not 1<=len(variables)<=8:raise ValueError('One to eight variables required')
    grid={};contracts={}
    for name,domain in variables.items():
        identifier(name)
        if name in ('self','result') or type(domain) is not dict or set(domain)!={'lower','upper','denominator'}:raise ValueError('Variable grid schema')
        lo,hi,den=(domain[n] for n in ('lower','upper','denominator'))
        if any(type(v) is not int for v in (lo,hi,den)) or not -1_000_000<=lo<=hi<=1_000_000 or not 1<=den<=1000:raise ValueError('Variable grid bounds')
        grid[name]=(lo,hi,den);contracts[name]=f'self >= ({lo}/{den}) && self <= ({hi}/{den})'
    reference=parse(raw['reference']);flat(reference,list(grid))
    candidates=raw.get('candidates',[])
    if type(candidates) is not list or len(candidates)>32:raise ValueError('Candidate budget')
    candidates=[parse(c) for c in candidates]
    for c in candidates:flat(c,list(grid))
    from omega_refine_check.syntax import evaluate
    training=raw.get('training',[])
    if type(training) is not list or not 1<=len(training)<=64:raise ValueError('Bounded training observations required')
    examples=[]
    for row in training:
        if type(row) is not dict or set(row)!={'inputs','output'} or set(row['inputs'])!=set(grid):raise ValueError('Training row schema')
        env={name:rational(value) for name,value in row['inputs'].items()}
        for name,q in env.items():
            lo,hi,den=grid[name]
            if not Fraction(lo,den)<=q<=Fraction(hi,den):raise ValueError('Training input outside domain')
        if evaluate(reference,env)!=rational(row['output']):raise ValueError('Training output disagrees with host oracle')
        examples.append({'inputs':{k:str(v) for k,v in env.items()},'output':str(rational(row['output']))})
    constants=raw.get('constants',['0','1','-1'])
    if type(constants) is not list or not 1<=len(constants)<=16:raise ValueError('Constant budget')
    constants=[str(rational(v)) for v in constants]
    operators=raw.get('operators',['+','-','*','/','neg'])
    if type(operators) is not list or len(set(operators))!=len(operators) or any(x not in ('+','-','*','/','neg','relu') for x in operators):raise ValueError('Known executable grammar required')
    extensions=raw.get('extensions',[])
    if type(extensions) is not list or len(extensions)>8 or any(type(e) is not str or len(e.encode())>8192 for e in extensions):raise ValueError('Opaque extension budget')
    return {'grid':grid,'contracts':contracts,'reference':reference,'reference_text':render(reference),'candidates':candidates,
            'training':examples,'search_spec':{'variables':contracts,'ensures':'true','examples':examples,'constants':constants,'operators':operators},'extensions':extensions}
