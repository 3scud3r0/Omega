"""Hygienic, strict specialization of pure rational/tensor expression templates.

Every argument is lowered once, in order, even when unused by the body. Types
and symbolic dimensions are checked for each concrete instantiation.
"""
from __future__ import annotations

from dataclasses import dataclass,replace,asdict
from fractions import Fraction
import hashlib
import json
from types import MappingProxyType

from .sintaxe import Numero,Variavel,Unario,Binario,Lista,Chamada,Comando,ALIAS,analisar,ErroOmega
from .typesystem import NumericType,TypeCheckError,infer_expression,infer_program
from .dimensions import _shape
from .typed_ir import _fields
from omega_security.encoding import canonical,decode

BUILTINS=frozenset({'zeros','identidade','relu','soma','dot','transposta'})


@dataclass(frozen=True)
class ExpansionLimits:
    source_bytes: int=256*1024
    steps: int=12000
    depth: int=128
    emitted_bindings: int=12000
    calls: int=4096
    specializations: int=128
    output_bytes: int=4*1024*1024

    def __post_init__(self):
        bounds={'source_bytes':(1,256*1024),'steps':(1,12000),'depth':(1,128),
                'emitted_bindings':(1,12000),'calls':(1,4096),
                'specializations':(1,128),'output_bytes':(1,4*1024*1024)}
        for name,(lower,upper) in bounds.items():
            value=getattr(self,name)
            if type(value) is not int or not lower<=value<=upper:
                raise TypeCheckError('Invalid generic expansion limit: '+name)


def _name(value):
    if type(value) is not str or not value.isidentifier() or value in ALIAS or value.startswith('__omega_coord_') or len(value)>128:
        raise TypeCheckError('Invalid generic identifier')


def _walk(expression):
    pending=[(expression,0)];count=0
    while pending:
        node,depth=pending.pop();count+=1
        if depth>200 or count>12000:raise TypeCheckError('Generic expression budget exceeded')
        yield node
        if type(node) is Binario:children=[node.esquerda,node.direita]
        elif type(node) is Unario:children=[node.argumento]
        elif type(node) is Lista:
            if type(node.elementos) is not tuple:raise TypeCheckError('Immutable generic list required')
            children=node.elementos
        elif type(node) is Chamada:
            _name(node.funcao)
            if type(node.argumentos) is not tuple:raise TypeCheckError('Immutable generic call required')
            children=node.argumentos
        elif type(node) is Numero:
            if type(node.valor) not in (int,Fraction):raise TypeCheckError('Exact generic literal required')
            value=Fraction(node.valor)
            if max(value.numerator.bit_length(),value.denominator.bit_length())>4096:raise TypeCheckError('Generic literal budget exceeded')
            children=[]
        elif type(node) is Variavel:_name(node.nome);children=[]
        else:raise TypeCheckError('Unsupported generic expression')
        pending.extend((child,depth+1) for child in reversed(children))


def render(expression):
    if type(expression) is Numero:return '('+str(expression.valor)+')'
    if type(expression) is Variavel:return expression.nome
    if type(expression) is Unario:return '('+expression.operador+render(expression.argumento)+')'
    if type(expression) is Binario:return '('+render(expression.esquerda)+expression.operador+render(expression.direita)+')'
    if type(expression) is Lista:return '['+','.join(render(x) for x in expression.elementos)+']'
    if type(expression) is Chamada:return expression.funcao+'('+','.join(render(x) for x in expression.argumentos)+')'
    raise TypeCheckError('Unsupported generic expression')


@dataclass(frozen=True)
class Parameter:
    name: str
    shape: tuple[int|str,...]
    def __post_init__(self):_name(self.name);_shape(self.shape)


@dataclass(frozen=True)
class Function:
    name: str
    parameters: tuple[Parameter,...]
    returns: tuple[int|str,...]
    body: object

    def __post_init__(self):
        _name(self.name);_shape(self.returns)
        if self.name in BUILTINS or type(self.parameters) is not tuple or not 1<=len(self.parameters)<=16 or any(type(p) is not Parameter for p in self.parameters):
            raise TypeCheckError('Invalid generic parameters')
        names=[p.name for p in self.parameters]
        if len(names)!=len(set(names)):raise TypeCheckError('Repeated generic parameter')
        dimensions={d for p in self.parameters for d in p.shape if type(d) is str}
        for name in dimensions:_name(name)
        if dimensions&set(names) or any(type(d) is str and d not in dimensions for d in self.returns):
            raise TypeCheckError('Unbound or captured generic dimension')
        for node in _walk(self.body):
            if type(node) is Variavel and node.nome not in dimensions|set(names):raise TypeCheckError('Generic body captures an undeclared value')
            if type(node) is Binario and node.operador not in ('+','-','*','/','^','@'):raise TypeCheckError('Unknown generic operator')
            if type(node) is Unario and node.operador!='-':raise TypeCheckError('Unknown generic unary operator')

    def bind(self,arguments):
        if type(arguments) is not tuple or len(arguments)!=len(self.parameters) or any(type(t) is not NumericType for t in arguments):
            raise TypeCheckError('Generic argument arity/type mismatch')
        dimensions={}
        for parameter,actual in zip(self.parameters,arguments):
            if len(parameter.shape)!=len(actual.shape):raise TypeCheckError('Generic argument rank mismatch')
            for pattern,value in zip(parameter.shape,actual.shape):
                if type(pattern) is int:
                    if pattern!=value:raise TypeCheckError('Generic concrete dimension mismatch')
                elif pattern in dimensions and dimensions[pattern]!=value:raise TypeCheckError('Generic symbolic dimensions disagree')
                else:dimensions[pattern]=value
        output=NumericType(tuple(dimensions[d] if type(d) is str else d for d in self.returns))
        return dimensions,output


class Registry:
    def __init__(self,functions):
        items=[]
        for function in functions:
            if len(items)>=64 or type(function) is not Function:raise TypeCheckError('Generic definition budget exceeded')
            items.append(function)
        functions=tuple(items)
        if not functions:raise TypeCheckError('Generic definitions required')
        table={f.name:f for f in functions}
        if len(table)!=len(functions):raise TypeCheckError('Repeated generic function')
        dependencies={}
        for name,function in table.items():
            calls={e.funcao for e in _walk(function.body) if type(e) is Chamada}
            if not calls<=set(table)|BUILTINS:raise TypeCheckError('Unknown function in generic body')
            dependencies[name]=calls&set(table)
        done=set();active=[]
        def visit(name):
            if name in active:raise TypeCheckError('Generic recursion cycle: '+' -> '.join([*active,name]))
            if name in done:return
            active.append(name)
            for child in sorted(dependencies[name]):visit(child)
            active.pop();done.add(name)
        for name in sorted(table):visit(name)
        self.functions=MappingProxyType(table)

    def specialize(self,name,arguments):
        if name not in self.functions:raise TypeCheckError('Unknown generic function')
        dimensions,result=self.functions[name].bind(arguments)
        return Specialization(name,arguments,tuple(sorted(dimensions.items())),result)

    @classmethod
    def from_dict(cls,value):
        try:canonical(value,max_bytes=1024*1024,max_nodes=10000)
        except (ValueError,TypeError,RecursionError) as exc:raise TypeCheckError('Generic definition data budget exceeded') from exc
        _fields(value,('format','schema_version','functions'))
        if value['format']!='omega-generics-1' or value['schema_version']!='1.0.0' or type(value['functions']) is not list or not 1<=len(value['functions'])<=64:
            raise TypeCheckError('Unsupported generic definition schema')
        functions=[]
        for f in value['functions']:
            _fields(f,('name','parameters','returns','body'))
            if type(f['parameters']) is not list or len(f['parameters'])>16 or type(f['returns']) is not list or type(f['body']) is not str or len(f['body'])>32768:
                raise TypeCheckError('Malformed generic function')
            parameters=[]
            for p in f['parameters']:
                _fields(p,('name','shape'))
                if type(p['shape']) is not list:raise TypeCheckError('Malformed generic parameter shape')
                parameters.append(Parameter(p['name'],tuple(p['shape'])))
            try:commands=analisar('tensor om_body='+f['body']+';')
            except (ValueError,RecursionError,ErroOmega) as exc:raise TypeCheckError('Generic expression parsing failed') from exc
            if len(commands)!=1 or commands[0].tipo!='tensor' or commands[0].nome!='om_body':raise TypeCheckError('A generic body must be one expression')
            functions.append(Function(f['name'],tuple(parameters),tuple(f['returns']),commands[0].expressao))
        return cls(functions)

    @classmethod
    def load(cls,path):
        with open(path,'rb') as stream:data=stream.read(1024*1024+1)
        return cls.from_bytes(data)

    @classmethod
    def from_bytes(cls,data):
        if type(data) is not bytes:raise TypeCheckError('Generic JSON bytes required')
        if len(data)>1024*1024:raise TypeCheckError('Generic definition byte budget exceeded')
        try:value=decode(data,max_bytes=1024*1024)
        except (ValueError,UnicodeError,RecursionError) as exc:raise TypeCheckError('Malformed generic JSON') from exc
        return cls.from_dict(value)

    def to_dict(self):
        return {'format':'omega-generics-1','schema_version':'1.0.0','functions':[
            {'name':f.name,'parameters':[{'name':p.name,'shape':list(p.shape)} for p in f.parameters],
             'returns':list(f.returns),'body':render(f.body)} for _,f in sorted(self.functions.items())]}


@dataclass(frozen=True)
class Specialization:
    function: str
    arguments: tuple[NumericType,...]
    dimensions: tuple[tuple[str,int],...]
    result: NumericType

    def to_dict(self):
        return {'function':self.function,'arguments':[t.to_dict() for t in self.arguments],
                'dimensions':dict(self.dimensions),'result':self.result.to_dict()}

    @property
    def sha256(self):return hashlib.sha256(canonical(self.to_dict())).hexdigest()


@dataclass(frozen=True)
class ExpandedProgram:
    source: str
    _manifest: bytes
    def manifest(self):return json.loads(self._manifest)


class _Expander:
    def __init__(self,registry,commands,limits):
        self.registry=registry;self.commands=commands;self.output=[];self.types={};self.reserved=set();self.next_id=0
        self.limits=limits;self.steps=limits.steps;self.calls=[];self.instances={};self.call_count=0;self.binding_count=0
        for command in commands:
            self.reserved.update((command.nome,command.parametro))
            for expression in (command.expressao,command.direita,command.taxa):
                if expression is not None:self.reserved.update(e.nome for e in _walk(expression) if type(e) is Variavel)
        for function in registry.functions.values():
            self.reserved.update(p.name for p in function.parameters)
            self.reserved.update(e.nome for e in _walk(function.body) if type(e) is Variavel)

    def bind(self,expression):
        if self.binding_count>=self.limits.emitted_bindings:raise TypeCheckError('Generic binding budget exceeded')
        self.binding_count+=1
        inferred=infer_expression(expression,self.types)
        while True:
            name='om_generic_'+str(self.next_id);self.next_id+=1
            if name not in self.reserved:break
        self.reserved.add(name);self.types[name]=inferred
        self.output.append(Comando('tensor',nome=name,expressao=expression))
        return Variavel(name)

    def literal(self,expression,environment):
        if type(expression) is Variavel and expression.nome in environment:expression=environment[expression.nome]
        if type(expression) is not Numero:raise TypeCheckError('A literal constructor dimension/exponent is required')
        return expression

    def expression(self,expression,environment=None,depth=0):
        self.steps-=1;environment={} if environment is None else environment
        if self.steps<0 or depth>self.limits.depth:raise TypeCheckError('Generic expansion budget exceeded')
        expand=lambda e:self.expression(e,environment,depth+1)
        if type(expression) is Numero:return self.bind(expression)
        if type(expression) is Variavel:
            if expression.nome in environment:
                result=environment[expression.nome]
                return self.bind(result) if type(result) is Numero else result
            infer_expression(expression,self.types);return expression
        if type(expression) is Lista:return self.bind(Lista(tuple(expand(e) for e in expression.elementos)))
        if type(expression) is Unario:return self.bind(Unario(expression.operador,expand(expression.argumento)))
        if type(expression) is Binario:
            left=expand(expression.esquerda)
            right=self.literal(expression.direita,environment) if expression.operador=='^' else expand(expression.direita)
            return self.bind(Binario(expression.operador,left,right))
        if type(expression) is Chamada:
            if expression.funcao in ('zeros','identidade'):
                return self.bind(Chamada(expression.funcao,tuple(self.literal(e,environment) for e in expression.argumentos)))
            # Strict left-to-right arguments, including ones unused by the body.
            arguments=tuple(expand(e) for e in expression.argumentos)
            if expression.funcao not in self.registry.functions:return self.bind(Chamada(expression.funcao,arguments))
            function=self.registry.functions[expression.funcao]
            self.call_count+=1
            if self.call_count>self.limits.calls:raise TypeCheckError('Generic call budget exceeded')
            types=tuple(self.types[e.nome] for e in arguments)
            specialization=self.registry.specialize(function.name,types)
            dimensions=dict(specialization.dimensions);expected=specialization.result
            key=(function.name,tuple(t.shape for t in types))
            if key not in self.instances and len(self.instances)>=self.limits.specializations:raise TypeCheckError('Generic specialization budget exceeded')
            self.instances.setdefault(key,None)
            local={p.name:a for p,a in zip(function.parameters,arguments)}
            local.update({name:Numero(Fraction(value)) for name,value in dimensions.items()})
            result=self.expression(function.body,local,depth+1)
            if self.types[result.nome]!=expected:raise TypeCheckError('Generic return shape disagrees with contract')
            record={**specialization.to_dict(),'specialization_sha256':specialization.sha256}
            self.calls.append(record);self.instances[key]=record
            return result
        raise TypeCheckError('Unsupported generic expression')

    def program(self):
        declarations={'parametro','parametro_tensor','tensor','vetor','matriz','perda'}
        for command in self.commands:
            if command.tipo in declarations|{'reescrever'}:
                if command.tipo in declarations and command.nome in self.types:raise TypeCheckError('Redeclared generic program symbol')
                expression=self.expression(command.expressao)
                self.output.append(replace(command,expressao=expression));self.types[command.nome]=self.types[expression.nome]
            elif command.taxa is not None:self.output.append(replace(command,taxa=self.expression(command.taxa)))
            else:
                for e in (command.expressao,command.direita):
                    if e is not None and any(type(n) is Chamada and n.funcao in self.registry.functions for n in _walk(e)):
                        raise TypeCheckError('Generic calls in universal proof ASTs are not supported')
                self.output.append(command)
        return self.output


def _command(c):
    if c.tipo=='parametro_tensor':return 'parametro '+c.parametro+' '+c.nome+'='+render(c.expressao)+';'
    if c.tipo in ('parametro','tensor','vetor','matriz','perda','reescrever'):return c.tipo+' '+c.nome+'='+render(c.expressao)+';'
    if c.tipo in ('gradiente','passo','passo_livre','passo_ruidoso'):
        result=c.tipo+' '+c.nome+' em '+c.parametro
        if c.taxa is not None:result+=' taxa '+render(c.taxa)
        if c.semente is not None:result+=' semente '+str(c.semente)
        return result+';'
    if c.tipo in ('gradientes','mostrar','verificar'):return c.tipo+' '+c.nome+';'
    if c.tipo in ('teorema','provar'):
        prefix='teorema '+c.nome+'=' if c.tipo=='teorema' else 'provar '
        return prefix+render(c.expressao)+'=='+render(c.direita)+';'
    raise TypeCheckError('Unsupported generic program command')


def expand(source,registry,*,limits=ExpansionLimits()):
    if type(limits) is not ExpansionLimits or type(registry) is not Registry or type(source) is not str:raise TypeCheckError('Typed generic expansion inputs required')
    if len(source)>limits.source_bytes or len(source.encode('utf-8'))>limits.source_bytes:raise TypeCheckError('Generic input budget exceeded')
    try:commands=analisar(source)
    except (ValueError,RecursionError,ErroOmega) as exc:raise TypeCheckError('Generic program parsing failed') from exc
    expander=_Expander(registry,commands,limits)
    expanded='\n'.join(_command(command) for command in expander.program())+'\n'
    if len(expanded.encode('utf-8'))>limits.output_bytes:raise TypeCheckError('Expanded source byte budget exceeded')
    types=infer_program(expanded)
    manifest={'format':'omega-specializations-1','input_sha256':hashlib.sha256(source.encode()).hexdigest(),
              'limits':asdict(limits),
              'expanded_sha256':hashlib.sha256(expanded.encode()).hexdigest(),'templates':registry.to_dict(),
              'calls':expander.calls,'instances':[v for _,v in sorted(expander.instances.items())],
              'original_symbols':sorted(c.nome for c in commands if c.tipo in ('parametro','parametro_tensor','tensor','vetor','matriz','perda')),
              'types':types.to_dict()}
    return ExpandedProgram(expanded,json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())


def project_ir(program,ir):
    """Remove implementation names/diagnostics, never nodes or computations.

    Strict unused arguments and node indices are preserved. The resulting IR
    is independently validated, including all original declaration commands.
    """
    from copy import deepcopy
    from .typed_ir import TypedIR
    if type(program) is not ExpandedProgram:raise TypeCheckError('Expanded program required')
    manifest=program.manifest()
    if hashlib.sha256(program.source.encode()).hexdigest()!=manifest['expanded_sha256']:
        raise TypeCheckError('Expansion source does not match its manifest')
    TypedIR.from_legacy(ir)
    names=set(manifest['original_symbols'])
    if not names<=set(ir['simbolos']):raise TypeCheckError('Original symbols missing from expansion')
    result=deepcopy(ir)
    result['simbolos']={name:index for name,index in result['simbolos'].items() if name in names}
    result['comandos']=[c for c in result['comandos'] if c['tipo']!='declaracao' or c['nome'] in names]
    TypedIR.from_legacy(result)
    return result


def project_result(program,result):
    """A semantic projection must still pass independent Lean admission."""
    from copy import deepcopy
    result=deepcopy(result)
    original=result['ir']
    encode=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    for certificate in result['certificates']:
        if certificate.get('tipo')!='identidade_nativa':
            if encode(certificate.get('ir'))!=encode(original):
                raise TypeCheckError('Certificate graph differs before specialization projection')
    result['ir']=project_ir(program,result['ir'])
    for certificate in result['certificates']:
        if certificate.get('tipo')!='identidade_nativa':certificate['ir']=deepcopy(result['ir'])
    names=set(program.manifest()['original_symbols'])
    result['values']={name:value for name,value in result['values'].items() if name in names}
    return result
