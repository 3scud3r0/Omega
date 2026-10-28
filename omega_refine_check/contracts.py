"""Universal rational contracts, typed declarations and division obligations."""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
from .syntax import Reader,tokens,parse,tree,identifier,substitute,lower
from .lean import prove,divisions
from omega_selfhost.proof_protocol import encode


@dataclass(frozen=True)
class Refinement:
    name:str
    width:int
    predicates:tuple

    def apply(self,value):
        if self.width>1:
            if value[0]!='vector' or len(value[1])!=self.width:raise ValueError('Refined tensor shape mismatch')
        elif value[0]=='vector':raise ValueError('Scalar refinement applied to a tensor')
        return [substitute(p,{'self':value}) for p in self.predicates]


def refinement_types(metadata):
    types={'Rational':Refinement('Rational',1,(('true',),))}
    for record in metadata['types']:
        name=identifier(record['name'])
        if name in types:raise ValueError('Duplicate refinement type')
        base=record['base'];parents=()
        if base==['Rational']:width=1
        elif len(base)==6 and base[:4]==['Tensor','[','Rational',','] and base[-1]==']' and base[4].isascii() and base[4].isdigit():
            width=int(base[4])
            if not 2<=width<=256:raise ValueError('Tensor refinement width must be in [2,256]')
        elif len(base)==1 and base[0] in types:
            parent=types[base[0]];width=parent.width;parents=parent.predicates
        else:raise ValueError('Unknown refinement base or unsupported tensor shape')
        predicate=parse(' '.join(record['predicate']))
        # Predicates are logical propositions, not partial arithmetic programs.
        if list(divisions(predicate)):raise ValueError('Refinement predicates require total arithmetic; move division into checked expressions')
        types[name]=Refinement(name,width,parents+(predicate,))
    return types


def verify_contract(variables,expression,ensures,*,requires=()):
    """Prove a candidate for every rational input satisfying explicit premises."""
    if type(variables) is not dict or not 0<=len(variables)<=32:raise ValueError('Bounded variable contracts required')
    names=[];environment={};assumptions=[]
    for name,predicate in variables.items():
        identifier(name)
        if name in ('self','result'):raise ValueError('Reserved contract identifier')
        names.append(name);value=('var',name);environment[name]=value
        pred=parse(predicate) if type(predicate) is str else tree(predicate)
        assumptions.append(substitute(pred,{'self':value,**environment}))
    for premise in requires:
        assumptions.append(substitute(parse(premise) if type(premise) is str else tree(premise),environment))
    candidate=tree(expression) if type(expression) is not str else parse(expression)
    candidate=substitute(candidate,environment)
    post=parse(ensures) if type(ensures) is str else tree(ensures)
    goal=substitute(post,{**environment,'result':candidate})
    obligations=[('!=',d,('const','0')) for d in divisions(candidate)]
    obligations.append(goal)
    proof=prove(names,assumptions,obligations)
    statement={'variables':variables,'expression':candidate,'ensures':post,'requires':list(requires)}
    return {**proof,'statement':statement,'statement_sha256':hashlib.sha256(encode(statement)).hexdigest(),
            'scope':'universal rational inputs under the declared premises; not arbitrary program equivalence'}


def program_obligations(source):
    metadata=lower(source);types=refinement_types(metadata)
    annotations={record['name']:record['type'] for record in metadata['bindings']}
    if len(annotations)!=len(metadata['bindings']):raise ValueError('Duplicate refined binding')
    reader=Reader(tokens(metadata['source']));environment={};names=[];assumptions=[];obligations=[];declared={}
    while reader.peek()!='<end>':
        kind=reader.take()
        if kind=='mostrar':
            name=identifier(reader.take());reader.need(';')
            if name not in environment:raise ValueError('Unknown output binding')
            continue
        if kind not in ('parametro','tensor','vetor','matriz','perda'):raise ValueError('Refined programs currently require pure declarations and mostrar')
        name=identifier(reader.take());reader.need('=');value=substitute(reader.expr(),environment);reader.need(';')
        if name in environment:raise ValueError('Duplicate declaration')
        local_goals=[('!=',d,('const','0')) for d in divisions(value)]
        alias=annotations.get(name)
        if alias is not None:
            if alias not in types:raise ValueError('Unknown refinement annotation')
            local_goals.extend(types[alias].apply(value))
        obligations.extend({'variables':list(names),'assumptions':list(assumptions),'goal':goal} for goal in local_goals)
        if kind=='parametro':
            if value[0]=='vector':
                coords=[]
                for i,_ in enumerate(value[1]):
                    coordinate=f'{name}__{i}'
                    if coordinate in names:raise ValueError('Parameter coordinate collision')
                    names.append(coordinate);coords.append(('var',coordinate))
                symbolic=('vector',tuple(coords))
            else:
                if name in names:raise ValueError('Parameter name collision')
                names.append(name);symbolic=('var',name)
            if len(names)>256:raise ValueError('Refined parameter coordinate budget exceeded')
            environment[name]=symbolic
            if alias is not None:assumptions.extend(types[alias].apply(symbolic))
        else:environment[name]=value
        declared[name]={'kind':kind,'type':alias,'expression':value}
    if set(annotations)-set(declared):raise ValueError('Dangling refinement annotation')
    if not obligations:obligations=[('true',)]
    return metadata,names,assumptions,obligations,declared


def check_program(source):
    metadata,names,premises,obligations,declared=program_obligations(source)
    proof=prove(names,premises,obligations)
    return {**proof,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'lowered_sha256':hashlib.sha256(metadata['source'].encode()).hexdigest(),
            'metadata':metadata,'declarations':declared,'scope':'pure rational/static-vector declarations under refined input contracts'}
