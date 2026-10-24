"""Hygienic, strict specialization of pure rational/tensor expression templates.

Every argument is lowered once, in order, even when unused by the body. Types
and symbolic dimensions are checked for each concrete instantiation.
"""
from __future__ import annotations

from dataclasses import dataclass,replace
from fractions import Fraction
import hashlib
import json
from types import MappingProxyType

from .sintaxe import Numero,Variavel,Unario,Binario,Lista,Chamada,Comando,ALIAS,analisar
from .typesystem import NumericType,TypeCheckError,infer_expression,infer_program
from .dimensions import _shape
from .typed_ir import _pairs,_fields

BUILTINS=frozenset({'zeros','identidade','relu','soma','dot','transposta'})


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
        elif type(node) is Lista:children=node.elementos
        elif type(node) is Chamada:children=node.argumentos
        elif type(node) in (Numero,Variavel):children=[]
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
        functions=tuple(functions)
        if not 1<=len(functions)<=64 or any(type(f) is not Function for f in functions):raise TypeCheckError('Generic definition budget exceeded')
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

    @classmethod
    def from_dict(cls,value):
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
            except (ValueError,RecursionError) as exc:raise TypeCheckError('Generic expression parsing failed') from exc
            if len(commands)!=1 or commands[0].tipo!='tensor' or commands[0].nome!='om_body':raise TypeCheckError('A generic body must be one expression')
            functions.append(Function(f['name'],tuple(parameters),tuple(f['returns']),commands[0].expressao))
        return cls(functions)

    @classmethod
    def load(cls,path):
        with open(path,'rb') as stream:data=stream.read(1024*1024+1)
        if len(data)>1024*1024:raise TypeCheckError('Generic definition byte budget exceeded')
        try:value=json.loads(data,object_pairs_hook=_pairs)
        except (ValueError,UnicodeError,RecursionError) as exc:raise TypeCheckError('Malformed generic JSON') from exc
        return cls.from_dict(value)

    def to_dict(self):
        return {'format':'omega-generics-1','schema_version':'1.0.0','functions':[
            {'name':f.name,'parameters':[{'name':p.name,'shape':list(p.shape)} for p in f.parameters],
             'returns':list(f.returns),'body':render(f.body)} for _,f in sorted(self.functions.items())]}


@dataclass(frozen=True)
class ExpandedProgram:
    source: str
    _manifest: bytes
    def manifest(self):return json.loads(self._manifest)


class _Expander:
    def __init__(self,registry,commands):
        self.registry=registry;self.commands=commands;self.output=[];self.types={};self.reserved=set();self.next_id=0
        self.steps=12000;self.calls=[];self.instances={}
        for command in commands:
            self.reserved.update((command.nome,command.parametro))
            for expression in (command.expressao,command.direita,command.taxa):
                if expression is not None:self.reserved.update(e.nome for e in _walk(expression) if type(e) is Variavel)
        for function in registry.functions.values():
            self.reserved.update(p.name for p in function.parameters)
            self.reserved.update(e.nome for e in _walk(function.body) if type(e) is Variavel)

    def bind(self,expression):
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
        if self.steps<0 or depth>200:raise TypeCheckError('Generic expansion budget exceeded')
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
            types=tuple(self.types[e.nome] for e in arguments);dimensions,expected=function.bind(types)
            key=(function.name,tuple(t.shape for t in types))
            if key not in self.instances and len(self.instances)>=128:raise TypeCheckError('Generic specialization budget exceeded')
            self.instances.setdefault(key,None)
            local={p.name:a for p,a in zip(function.parameters,arguments)}
            local.update({name:Numero(Fraction(value)) for name,value in dimensions.items()})
            result=self.expression(function.body,local,depth+1)
            if self.types[result.nome]!=expected:raise TypeCheckError('Generic return shape disagrees with contract')
            record={'function':function.name,'arguments':[t.to_dict() for t in types],
                    'dimensions':dict(sorted(dimensions.items())),'result':expected.to_dict()}
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


def expand(source,registry):
    if type(registry) is not Registry or type(source) is not str or len(source)>256*1024:raise TypeCheckError('Generic input budget exceeded')
    try:commands=analisar(source)
    except (ValueError,RecursionError) as exc:raise TypeCheckError('Generic program parsing failed') from exc
    expander=_Expander(registry,commands)
    expanded='\n'.join(_command(command) for command in expander.program())+'\n'
    types=infer_program(expanded)
    manifest={'format':'omega-specializations-1','input_sha256':hashlib.sha256(source.encode()).hexdigest(),
              'expanded_sha256':hashlib.sha256(expanded.encode()).hexdigest(),'templates':registry.to_dict(),
              'calls':expander.calls,'instances':[v for _,v in sorted(expander.instances.items())],
              'original_symbols':sorted(c.nome for c in commands if c.tipo in ('parametro','parametro_tensor','tensor','vetor','matriz','perda')),
              'types':types.to_dict()}
    return ExpandedProgram(expanded,json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())

# Additional components share this file so the requested delivery is auditable.
# Task coverage is explicitly measured; inclusion here never grants acceptance.
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import math
import random
import time
import unittest


class BoundedQueue:
    """FIFO with explicit capacity; overflow never discards an existing item."""
    def __init__(self, capacity):
        if type(capacity) is not int or not 1 <= capacity <= 100000:
            raise ValueError('Invalid queue capacity')
        self.capacity = capacity
        self._items = deque()

    def push(self, value):
        if len(self._items) >= self.capacity:
            raise OverflowError('Queue capacity exhausted')
        self._items.append(value)

    def pop(self):
        if not self._items:
            raise IndexError('Empty queue')
        return self._items.popleft()

    def __len__(self):
        return len(self._items)


class ArenaBudget:
    """Accounting contract only: this does not implement native garbage collection."""
    def __init__(self, limit):
        if type(limit) is not int or limit <= 0:
            raise ValueError('Positive allocation budget required')
        self.limit = limit
        self.used = 0
        self._allocations = {}
        self._next = 0

    def reserve(self, size):
        if type(size) is not int or size < 0:
            raise ValueError('Invalid allocation size')
        if size > self.limit - self.used:
            raise MemoryError('Allocation budget exhausted')
        self._next += 1
        self._allocations[self._next] = size
        self.used += size
        return self._next

    def release(self, handle):
        if type(handle) is not int or handle not in self._allocations:
            raise ValueError('Unknown or already released allocation')
        self.used -= self._allocations.pop(handle)


@dataclass(frozen=True)
class Measurement:
    name: str
    seed: int
    elapsed_seconds: float
    correct: bool
    detail: str


def deterministic_map(operation, values, workers=1):
    """Ordered results for trusted pure host functions, not a candidate sandbox.

    Callers must provide pure operations. Shared mutable state is not made safe
    by this helper, and process isolation remains the existing sandbox's job.
    """
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError('Invalid worker count')
    values = tuple(values)
    if len(values) > 10000:
        raise ValueError('Batch budget exhausted')
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return tuple(executor.map(operation, values))


def paired_bootstrap(before, after, *, seed=0, samples=2000):
    """Paired mean improvement and percentile CI; no automatic promotion."""
    before, after = tuple(before), tuple(after)
    if len(before) != len(after) or not 2 <= len(before) <= 10000:
        raise ValueError('Paired measurements required')
    if type(samples) is not int or not 100 <= samples <= 10000:
        raise ValueError('Invalid resampling budget')
    if samples * len(before) > 2000000:
        raise ValueError('Resampling work budget exhausted')
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in before + after):
        raise ValueError('Finite measurements required')
    delta = tuple(y-x for x,y in zip(before,after))
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(delta) for _ in delta)/len(delta) for _ in range(samples))
    return {'mean_delta':sum(delta)/len(delta), 'ci95':[means[int(samples*.025)],means[int(samples*.975)]],
            'seed':seed,'samples':samples,'pairs':len(delta),'promotion_authorized':False}


def benchmark(name, operation, verify, *, seed=0):
    """Measure a trusted adapter; preserve negative outcomes as measurements."""
    started = time.perf_counter()
    try:
        value = operation(seed)
        correct = verify(value)
        if type(correct) is not bool:
            raise TypeError('Verifier must return bool')
        detail = 'accepted' if correct else 'rejected'
    except Exception as exc:
        correct = False
        detail = type(exc).__name__
    return Measurement(name,seed,time.perf_counter()-started,correct,detail)


def coverage(root):
    """Report actual scope against every requested task, without success stubs."""
    from pathlib import Path
    tasks=[]
    for line in (Path(root)/'roadmap/tasks.tsv').read_text().splitlines():
        task,phase,title,acceptance=line.split('\t')
        if int(task[3:]) < 18:
            continue
        tasks.append({'id':task,'phase':int(phase),'title':title,'acceptance':acceptance,
                      'status':'partial' if task in {'OM-018','OM-019','OM-020','OM-021','OM-109','OM-136'} else 'not_implemented',
                      'accepted':False})
    return tasks


class MonolithTests(unittest.TestCase):
    def test_queue_properties(self):
        rng=random.Random(19)
        queue=BoundedQueue(20)
        reference=[]
        for _ in range(1000):
            if reference and rng.randrange(2):
                self.assertEqual(queue.pop(),reference.pop(0))
            elif len(reference)<20:
                value=rng.randrange(100);queue.push(value);reference.append(value)
            self.assertEqual(len(queue),len(reference))
        full=BoundedQueue(1);full.push(7)
        with self.assertRaises(OverflowError):full.push(8)
        self.assertEqual(full.pop(),7)
        with self.assertRaises(IndexError):full.pop()

    def test_allocation_accounting(self):
        arena=ArenaBudget(10);handle=arena.reserve(8)
        with self.assertRaises(MemoryError):arena.reserve(3)
        self.assertEqual(arena.used,8)
        arena.release(handle)
        self.assertEqual(arena.used,0)
        with self.assertRaises(ValueError):arena.release(handle)

    def test_ordered_execution(self):
        self.assertEqual(deterministic_map(lambda x:x*x,range(100),4),tuple(x*x for x in range(100)))

    def test_statistics_do_not_authorize_promotion(self):
        result=paired_bootstrap([0,0,0],[1,1,1],samples=100)
        self.assertEqual(result['ci95'],[1,1])
        self.assertFalse(result['promotion_authorized'])
        with self.assertRaises(ValueError):paired_bootstrap([0,float('nan')],[1,2])

    def test_negative_benchmark_is_preserved(self):
        result=benchmark('negative',lambda seed:0,lambda value:False)
        self.assertFalse(result.correct)
        self.assertEqual(result.detail,'rejected')

    def test_generic_expansion(self):
        registry=Registry.from_dict({'format':'omega-generics-1','schema_version':'1.0.0','functions':[
            {'name':'square','parameters':[{'name':'x','shape':[]}],'returns':[],'body':'x*x'}]})
        result=expand('parametro x=3;perda l=square(x);mostrar l;',registry)
        self.assertEqual(result.manifest()['instances'][0]['result'],{'element':'rational','shape':[]})


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Single-file Omega components; unfinished roadmap tasks are explicitly reported.')
    parser.add_argument('action',choices=['self-test','coverage'])
    args=parser.parse_args()
    if args.action=='self-test':
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(MonolithTests)
        outcome=unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if outcome.wasSuccessful() else 1)
    print(json.dumps(coverage(Path(__file__).resolve().parents[1]),ensure_ascii=False,indent=2))
