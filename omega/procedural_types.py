"""Bounded, closed-world type analysis of the procedural bootstrap dialect.

Calls are specialized by their abstract arguments. The pass never evaluates
user arithmetic, performs I/O, or runs an Omega function. Unsupported recursive
container types and unstable loop invariants are rejected, not guessed.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from fractions import Fraction
from contextvars import ContextVar

from .typesystem import TypeCheckError
from omega_selfhost.bootstrap import Bootstrap,BUILTINS

_budget=ContextVar('omega_procedural_type_budget',default=None)


def meter():
    callback=_budget.get()
    if callback is not None:callback()


def literal_index(ast):
    if ast[0]!='n' or len(ast[1])>32:return -1
    number=Fraction(ast[1])
    return int(number) if number.denominator==1 else -1


@dataclass(eq=False)
class Type:
    kind: str
    element: Type|None=None
    fields: dict[str,Type]=field(default_factory=dict)
    alternatives: tuple[Type,...]=()
    slots: list[Type]|None=None
    binding: Type|None=None
    encoded: Type|None=None
    opaque: bool=False
    escaped: bool=False
    permitted: frozenset[str]|None=None


def resolved(t):
    meter()
    while t.kind=='variable' and t.binding is not None:meter();t=t.binding
    return t


def signature(t,seen=None):
    t=resolved(t);seen={} if seen is None else seen
    if id(t) in seen:return ('reference',seen[id(t)])
    seen[id(t)]=len(seen)
    return (t.kind,signature(t.element,seen) if t.element else None,
            tuple((k,signature(v,seen)) for k,v in sorted(t.fields.items())),
            tuple(signature(v,seen) for v in t.alternatives),
            tuple(signature(v,seen) for v in t.slots) if t.slots is not None else None,
            signature(t.encoded,seen) if t.encoded else None,t.opaque,t.escaped,
            tuple(sorted(t.permitted)) if t.permitted is not None else None)


def variants(t):
    meter()
    t=resolved(t)
    if t.kind=='union':return [v for child in t.alternatives for v in variants(child)]
    if t.kind=='json':
        if not t.alternatives:
            t.alternatives=(Type('number'),Type('string'),Type('list',element=Type('json'),opaque=True),
                            Type('object',element=Type('json'),opaque=True))
        return list(t.alternatives)
    return [t]


def symbolic(t,seen=None):
    t=resolved(t)
    if t.kind=='variable':return True
    seen=set() if seen is None else seen
    if id(t) in seen:return False
    seen.add(id(t))
    return any(symbolic(v,seen) for v in [*t.fields.values(),*t.alternatives,
               *(t.slots or []),*([t.element] if t.element else [])])


def join(types):
    entries={}
    for value in types:
        for t in variants(value):
            if t.kind=='bottom':continue
            key=('owner',id(t)) if t.kind in ('list','object') or symbolic(t) else signature(t)
            entries.setdefault(key,t)
    if not entries:return Type('bottom')
    if len(entries)==1:return next(iter(entries.values()))
    return Type('union',alternatives=tuple(sorted(entries.values(),key=lambda t:repr(signature(t)))))


def occurs(variable,t,seen=None):
    t=resolved(t)
    if t is variable:return True
    seen=set() if seen is None else seen
    if id(t) in seen:return False
    seen.add(id(t))
    return any(occurs(variable,c,seen) for c in [*t.fields.values(),*t.alternatives,
               *(t.slots or []),*([t.element] if t.element else []),*([t.encoded] if t.encoded else [])])


def unify(a,b):
    a=resolved(a);b=resolved(b)
    if a is b or a.kind=='bottom' or b.kind=='bottom':return
    if a.kind=='variable':
        if occurs(a,b):raise TypeCheckError('Recursive container type is not supported')
        if a.permitted is not None:
            if b.kind=='variable':
                allowed=a.permitted if b.permitted is None else a.permitted & b.permitted
                if not allowed:raise TypeCheckError('Incompatible procedural type constraints')
                b.permitted=allowed
            elif not {t.kind for t in variants(b)}<=a.permitted:
                raise TypeCheckError('A value violates its guarded type constraint')
        if a.escaped:escape(b)
        a.binding=b;return
    if b.kind=='variable':unify(b,a);return
    if a.kind!=b.kind:raise TypeCheckError(f'Incompatible procedural types: {a.kind} and {b.kind}')
    if a.kind in ('list','object') and (a.opaque or b.opaque):
        escape(a);escape(b)
    if a.kind=='list':
        a.slots=b.slots=None
        if a.element and b.element:unify(a.element,b.element)
        elif a.element:b.element=a.element
    if a.kind=='object':
        for name,t in list(b.fields.items()):
            if name in a.fields:unify(a.fields[name],t)
            else:a.fields[name]=t
        b.fields=a.fields
        if a.element and b.element:unify(a.element,b.element)
        elif a.element:b.element=a.element
    if a.kind=='union' and signature(a)!=signature(b):
        raise TypeCheckError('Incompatible union assignments')
    if a.kind=='union':
        for left,right in zip(a.alternatives,b.alternatives):unify(left,right)
    if a.kind=='string':b.encoded=None
    if occurs(a,b):raise TypeCheckError('Recursive container type is not supported')
    a.kind='variable';a.binding=b


def escape(t,seen=None):
    """Values stored in opaque JSON can be reached through untracked aliases."""
    t=resolved(t);seen=set() if seen is None else seen
    if id(t) in seen:return
    seen.add(id(t))
    if t.kind=='variable':t.escaped=True
    if t.kind=='union':
        for value in t.alternatives:escape(value,seen)
    if t.kind in ('list','object') and not t.opaque:
        for child in [*t.fields.values(),*(t.slots or []),*([t.element] if t.element else [])]:escape(child,seen)
        t.opaque=True;t.fields={};t.slots=None;t.element=Type('json')


def snapshot(t,memo=None):
    """JSON round trips reconstruct values; they do not alias live containers."""
    t=resolved(t);memo={} if memo is None else memo
    if id(t) in memo:return memo[id(t)]
    if t.kind=='variable':return Type('json')
    result=Type(t.kind);memo[id(t)]=result
    result.element=snapshot(t.element,memo) if t.element else None
    result.fields={name:snapshot(value,memo) for name,value in t.fields.items()}
    result.alternatives=tuple(snapshot(value,memo) for value in t.alternatives)
    result.slots=[snapshot(value,memo) for value in t.slots] if t.slots is not None else None
    result.encoded=snapshot(t.encoded,memo) if t.encoded else None
    result.opaque=t.opaque
    return result


class Scope:
    def __init__(self,parent=None):self.parent=parent;self.values={};self.declared=set();self.dead=parent.dead if parent else False
    def get(self,name):
        if name in self.values:return self.values[name]
        if self.parent:return self.parent.get(name)
        raise TypeCheckError('Undeclared procedural variable: '+name)
    def all_values(self):
        return [*self.values.values(),*(self.parent.all_values() if self.parent else [])]


@dataclass(frozen=True)
class Specialization:
    function: str
    arguments: tuple
    result: tuple
    mode: str='contextual'
    arguments_after: tuple=()


class Checker:
    def __init__(self,functions):
        self.functions={};self.active={};self.steps=120000;self.calls=0;self.visited=set();self.summaries=[];self.generic=False
        for name,parameters,body in functions:
            if name in self.functions or name in BUILTINS or len(parameters)!=len(set(parameters)):
                raise TypeCheckError('Repeated/reserved function or parameter: '+name)
            self.functions[name]=(parameters,body)
        if 'principal' not in self.functions:raise TypeCheckError('principal is required')
        if self.functions['principal'][0]:raise TypeCheckError('principal takes no arguments')

    def tick(self):
        self.steps-=1
        if self.steps<0:raise TypeCheckError('Procedural inference budget exceeded')

    def require(self,value,allowed):
        value=resolved(value)
        if value.kind=='variable':
            # Ambiguous unconstrained arithmetic is conservatively numeric.
            choices=set(allowed) if value.permitted is None else set(allowed)&value.permitted
            if not choices:raise TypeCheckError('A guarded value cannot have the required type')
            tag='number' if 'number' in choices else sorted(choices)[0]
            unify(value,Type(tag,element=Type('variable') if tag=='list' else None))
            value=resolved(value)
        if any(t.kind not in allowed and t.kind!='bottom' for t in variants(value)):
            raise TypeCheckError('Expected '+ '/'.join(sorted(allowed))+'; obtained '+value.kind)
        return value

    def refined(self,scope,condition,truth):
        child=Scope(scope)
        if condition[0]=='un' and condition[1]=='!':return self.refined(scope,condition[2],not truth)
        if condition[0]=='bin' and ((condition[1]=='&&' and truth) or (condition[1]=='||' and not truth)):
            return self.refined(self.refined(scope,condition[2],truth),condition[3],truth)
        if condition[0]=='call' and condition[1] in ('isnum','isstr','islist') and len(condition[2])==1:
            argument=condition[2][0]
            if argument[0]=='v':
                tags={'isnum':'number','isstr':'string','islist':'list'}
                value=scope.get(argument[1]);tag=tags[condition[1]]
                value=resolved(value)
                if value.kind=='variable':
                    choices=value.permitted if value.permitted is not None else frozenset({'number','string','list','object'})
                    choices=frozenset(t for t in choices if (t==tag)==truth)
                    escape(value)
                    narrowed=Type('variable',permitted=choices,escaped=True) if choices else Type('bottom')
                else:narrowed=join([t for t in variants(value) if (t.kind==tag)==truth])
                child.values[argument[1]]=narrowed
                if resolved(child.values[argument[1]]).kind=='bottom':child.dead=True
        return child

    def index(self,receiver,key_ast,key):
        receiver=resolved(receiver)
        if receiver.kind=='variable':
            unify(receiver,Type('object') if resolved(key).kind=='string' else Type('list',element=Type('variable')))
            receiver=resolved(receiver)
        results=[]
        for target in variants(receiver):
            if target.kind=='bottom':continue
            if target.kind=='string':self.require(key,{'number'});results.append(Type('string'))
            elif target.kind=='list':
                self.require(key,{'number'})
                if target.opaque:results.append(Type('json'));continue
                index=literal_index(key_ast)
                if target.slots is not None and 0<=index<len(target.slots):results.append(target.slots[index])
                else:
                    if target.element is None:target.element=Type('variable')
                    results.append(target.element)
            elif target.kind=='object':
                self.require(key,{'string'})
                if target.opaque:results.append(Type('json'));continue
                if key_ast[0]=='s':
                    name=key_ast[1]
                    if name not in target.fields:target.fields[name]=target.element or Type('variable')
                    results.append(target.fields[name])
                else:results.append(join([*target.fields.values(),*([target.element] if target.element else [])]) if target.fields or target.element else Type('variable'))
            else:raise TypeCheckError('Indexing requires a string, list or object')
        return join(results)

    def builtin(self,name,args,asts):
        arities={'list':0,'obj':0,'len':1,'get':2,'put':3,'push':2,'has':2,'keys':1,
                 'text':1,'number':1,'ident':1,'decimal':2,'isnum':1,'isstr':1,'islist':1,
                 'slice':3,'join':2,'contains':2,'arg':1,'argc':0,'read':1,'write':2,
                 'print':1,'fail':1,'json':1,'parsejson':1,'qnum':1,'qden':1,'qfloor':1,'qbits':1,'monotonic_ns':0,'unix_time':0,'readline':0,'flush':0,
                 'root_read':2,'root_write':3,'root_exists':2,'sha256':1,'file_sha256':2,'append_cas':4,'ed25519_verify':3,'ed25519_sign':3}
        if len(args)!=arities[name]:raise TypeCheckError('Wrong builtin arity: '+name)
        if any(resolved(t).kind=='bottom' for t in args):return Type('bottom')
        number=lambda:Type('number');string=lambda:Type('string')
        if name in ('qnum','qden','qfloor','qbits'):
            self.require(args[0],{'number'});return number()
        if name in ('monotonic_ns','unix_time','flush'):return number()
        if name=='readline':return Type('object',fields={'eof':number(),'line':string()})
        if name in ('root_read','root_write','root_exists','sha256','file_sha256','append_cas','ed25519_verify','ed25519_sign'):
            for value in args:self.require(value,{'string'})
            return number() if name in ('root_write','root_exists','append_cas','ed25519_verify') else string()
        if name=='list':return Type('list',element=Type('variable'),slots=[])
        if name=='obj':return Type('object')
        if name in ('isnum','isstr','islist','argc'):return number()
        if name=='json':return Type('string',encoded=snapshot(args[0]))
        if name=='parsejson':
            value=self.require(args[0],{'string'})
            return snapshot(value.encoded) if value.kind=='string' and value.encoded else Type('json')
        if name in ('text','number','print','fail'):
            self.require(args[0],{'number','string'})
            return Type('bottom') if name=='fail' else string() if name=='text' else number()
        if name in ('ident','read'):
            self.require(args[0],{'string'});return string() if name=='read' else number()
        if name=='arg':self.require(args[0],{'number'});return string()
        if name=='write':
            for t in args:self.require(t,{'string'})
            return number()
        if name=='len':self.require(args[0],{'string','list','object'});return number()
        if name=='get':return self.index(args[0],asts[1],args[1])
        if name=='keys':self.require(args[0],{'object'});return Type('list',element=string())
        if name=='has':self.require(args[0],{'object'});self.require(args[1],{'string'});return number()
        if name=='decimal':self.require(args[0],{'string'});self.require(args[1],{'number'});return number()
        if name=='slice':
            self.require(args[0],{'string','list'})
            for t in args[1:]:self.require(t,{'number'})
            return join([Type('string') if t.kind=='string' else Type('list',element=t.element) for t in variants(args[0])])
        if name=='join':
            value=self.require(args[0],{'list'});self.require(args[1],{'string'})
            for t in variants(value):
                if t.element:self.require(t.element,{'string'})
            return string()
        if name=='contains':
            value=self.require(args[0],{'string','list'})
            if any(t.kind=='string' for t in variants(value)):self.require(args[1],{'string'})
            return number()
        if name=='push':
            value=self.require(args[0],{'list'})
            for t in variants(value):
                if t.opaque:escape(args[1]);continue
                if occurs(t,args[1]):raise TypeCheckError('Recursive container type is not supported')
                t.element=args[1] if t.element is None or resolved(t.element).kind=='variable' else join([t.element,args[1]])
                if t.slots is not None:t.slots.append(args[1])
            return value
        if name=='put':
            if resolved(args[0]).kind=='variable':
                unify(args[0],Type('object') if resolved(args[1]).kind=='string' else Type('list',element=Type('variable')))
            value=self.require(args[0],{'list','object'})
            for t in variants(value):
                if t.opaque:
                    self.require(args[1],{'number'} if t.kind=='list' else {'string'})
                    escape(args[2]);continue
                if occurs(t,args[2]):raise TypeCheckError('Recursive container type is not supported')
                if t.kind=='list':
                    self.require(args[1],{'number'})
                    if t.element is None:t.element=args[2]
                    if t.slots:
                        index=literal_index(asts[1])
                        slots=[t.slots[index]] if 0<=index<len(t.slots) else t.slots
                        for slot in slots:unify(slot,args[2])
                    else:unify(t.element,args[2])
                else:
                    self.require(args[1],{'string'})
                    if asts[1][0]=='s':
                        key=asts[1][1]
                        if key in t.fields:unify(t.fields[key],args[2])
                        else:
                            if t.element:self.require(args[2],{x.kind for x in variants(t.element)})
                            t.fields[key]=args[2]
                    else:
                        for field_type in t.fields.values():unify(field_type,args[2])
                        t.element=join([*([t.element] if t.element else []),args[2]])
            return value
        raise TypeCheckError('Unsupported builtin: '+name)

    def expression(self,expr,scope):
        self.tick();kind=expr[0]
        if kind=='n':return Type('number')
        if kind=='s':return Type('string')
        if kind=='v':return scope.get(expr[1])
        if kind=='list':
            slots=[self.expression(e,scope) for e in expr[1]]
            return Type('list',element=join(slots) if slots else Type('variable'),slots=slots)
        if kind=='index':return self.index(self.expression(expr[1],scope),expr[2],self.expression(expr[2],scope))
        if kind=='call':
            arguments=[self.expression(e,scope) for e in expr[2]]
            return self.builtin(expr[1],arguments,expr[2]) if expr[1] in BUILTINS else self.call(expr[1],arguments)
        if kind=='un':
            value=self.expression(expr[2],scope)
            if expr[1]=='-':self.require(value,{'number'})
            return Type('number')
        left=self.expression(expr[2],scope);operator=expr[1]
        right=self.expression(expr[3],self.refined(scope,expr[2],operator=='&&') if operator in ('&&','||') else scope)
        if operator in ('==','!=','&&','||'):return Type('number')
        if resolved(left).kind=='bottom' or resolved(right).kind=='bottom':return Type('bottom')
        allowed={'number','string'} if operator in ('+','<','<=','>','>=') else {'number'}
        left=self.require(left,allowed);right=self.require(right,allowed)
        pairs={(a.kind,b.kind) for a in variants(left) for b in variants(right)}
        if any(a!=b for a,b in pairs):raise TypeCheckError('Operator operands may have different types: '+operator)
        return left if operator=='+' else Type('number')

    def forget_slots(self,value,seen=None):
        value=resolved(value);seen=set() if seen is None else seen
        if id(value) in seen:return
        seen.add(id(value))
        if value.kind=='list':value.slots=None
        for child in [*value.fields.values(),*value.alternatives,*([value.element] if value.element else [])]:self.forget_slots(child,seen)

    def widen(self,value,seen=None):
        value=resolved(value);seen=set() if seen is None else seen
        if id(value) in seen:return
        seen.add(id(value))
        if value.kind=='list' and value.element and not value.opaque:
            groups={}
            for child in variants(value.element):
                key=signature(child)
                if key in groups and child.kind in ('list','object'):unify(groups[key],child)
                else:groups[key]=child
            value.element=join(groups.values())
        for child in [*value.fields.values(),*value.alternatives,*([value.element] if value.element else [])]:self.widen(child,seen)

    def block(self,statements,scope,loop=False):
        returns=[]
        if scope.dead:return returns,False
        declared=set(scope.declared)
        for statement in statements:
            self.tick();kind=statement[0]
            if kind in ('var','set'):
                value=self.expression(statement[2],scope)
                if kind=='var':
                    if statement[1] in declared:raise TypeCheckError('Repeated local variable: '+statement[1])
                    declared.add(statement[1])
                    scope.values[statement[1]]=value
                else:unify(scope.get(statement[1]),value)
            elif kind=='return':returns.append(self.expression(statement[1],scope));return returns,False
            elif kind=='expr':
                if resolved(self.expression(statement[1],scope)).kind=='bottom':return returns,False
            elif kind=='break':
                if not loop:raise TypeCheckError('parar outside a loop')
                return returns,False
            elif kind=='se':
                self.expression(statement[1],scope)
                left,lf=self.block(statement[2],self.refined(scope,statement[1],True),loop)
                right,rf=self.block(statement[3],self.refined(scope,statement[1],False),loop)
                returns.extend([*left,*right])
                if not lf and not rf:return returns,False
                if not lf:scope=self.refined(scope,statement[1],False)
                elif not rf:scope=self.refined(scope,statement[1],True)
            elif kind=='enquanto':
                self.expression(statement[1],scope)
                for t in scope.all_values():self.forget_slots(t)
                for _ in range(8):
                    before=tuple(signature(t) for t in scope.all_values())
                    values,_=self.block(statement[2],self.refined(scope,statement[1],True),True)
                    returns.extend(values)
                    for t in scope.all_values():self.widen(t)
                    after=tuple(signature(t) for t in scope.all_values())
                    if before==after:break
                else:raise TypeCheckError('Loop type invariant did not converge')
            else:raise TypeCheckError('Unknown procedural statement')
        return returns,True

    def call(self,name,arguments):
        self.tick()
        if name not in self.functions:raise TypeCheckError('Unknown procedural function: '+name)
        parameters,body=self.functions[name]
        if len(arguments)!=len(parameters):raise TypeCheckError('Wrong function arity: '+name)
        if any(resolved(t).kind=='bottom' for t in arguments):return Type('bottom')
        key=(name,tuple(signature(t) for t in arguments))
        if key in self.active:
            # Recursive effects have not reached a fixed point. Do not reuse
            # precise heap facts for objects the recursive call may mutate.
            for argument in arguments:escape(argument)
            return self.active[key]
        self.calls+=1
        if self.calls>100:raise TypeCheckError('Procedural call analysis depth exceeded')
        result=Type('number') if name=='principal' else Type('variable')
        self.active[key]=result;self.visited.add(name);scope=Scope();scope.values=dict(zip(parameters,arguments));scope.declared=set(parameters)
        try:
            values,falls=self.block(body,scope)
            if falls:values.append(Type('number'))
            values=[value for value in values if resolved(value) is not resolved(result)]
            inferred=join(values)
            unify(result,inferred)
            self.summaries.append(Specialization(name,key[1],signature(result),
                                                'uninstantiated' if self.generic else 'contextual',
                                                tuple(signature(argument) for argument in arguments)))
            return resolved(result)
        finally:
            self.calls-=1;del self.active[key]


@dataclass(frozen=True)
class ProceduralTypes:
    functions: tuple[str,...]
    checked_functions: tuple[str,...]
    specializations: tuple[Specialization,...]
    reachable_functions: tuple[str,...]
    def to_dict(self):return {'format':'omega-procedural-types-1','functions':list(self.functions),
                             'checked_functions':list(self.checked_functions),
                             'checked_reachable_functions':list(self.reachable_functions),
                             'specializations':[{'function':s.function,'arguments':s.arguments,
                                                 'arguments_after':s.arguments_after,
                                                 'result':s.result,'mode':s.mode} for s in self.specializations],
                             'entry_return':'number','mode':'bounded-closed-world'}


def infer_procedural(source):
    if not isinstance(source,str) or len(source)>256*1024:raise TypeCheckError('Procedural source budget exceeded')
    try:functions=Bootstrap(source).parse()
    except (ValueError,IndexError,RecursionError) as exc:raise TypeCheckError('Invalid or excessively deep procedural source') from exc
    checker=Checker(functions)
    token=_budget.set(checker.tick)
    try:
        try:
            checker.call('principal',[])
            reachable=tuple(sorted(checker.visited));checker.generic=True
            for name,(parameters,_) in checker.functions.items():
                if name not in checker.visited:checker.call(name,[Type('variable') for _ in parameters])
        except RecursionError:raise TypeCheckError('Procedural inference depth exceeded') from None
    finally:_budget.reset(token)
    return ProceduralTypes(tuple(checker.functions),tuple(sorted(checker.visited)),tuple(checker.summaries),reachable)
