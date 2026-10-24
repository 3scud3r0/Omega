"""Canonical, versioned tensor IR. Validation is not proof admission.

Legacy import is explicit and lossless. Unknown versions, fields, duplicate
JSON keys and noncanonical rational literals fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re

from .dimensions import certify_graph_shapes
from .typesystem import NumericType,RATIONAL,TypeCheckError,infer_operation

MAX_BYTES=16*1024*1024
FORMAT='omega-typed-ir-1'
VERSION='1.0.0'


def _fields(value,required,optional=()):
    if type(value) is not dict or not set(required)<=set(value)<=set(required)|set(optional):
        raise TypeCheckError('Missing or unknown IR fields')


def _name(value):
    if type(value) is not str or not value.isidentifier() or len(value)>256:
        raise TypeCheckError('Invalid IR identifier')
    return value


def _tree(value):
    pending=[(value,0)];count=0
    while pending:
        item,depth=pending.pop();count+=1
        if depth>220 or count>500000:raise TypeCheckError('IR structure budget exceeded')
        if type(item) is dict:
            if any(type(k) is not str or len(k)>256 for k in item):raise TypeCheckError('Invalid IR object key')
            pending.extend((v,depth+1) for v in item.values())
        elif type(item) is list:pending.extend((v,depth+1) for v in item)
        elif type(item) is str:
            if len(item)>10000:raise TypeCheckError('IR string budget exceeded')
            try:item.encode('utf-8')
            except UnicodeError:raise TypeCheckError('Invalid IR Unicode') from None
        elif type(item) is not int or not 0<=item<2**32:
            raise TypeCheckError('IR values must be objects, arrays, strings or bounded natural numbers')


def _integer(text):
    sign=-1 if text.startswith('-') else 1
    digits=text[1:] if sign<0 else text
    result=0
    for start in range(0,len(digits),64):
        block=digits[start:start+64];result=result*10**len(block)+int(block)
    return sign*result


def _rational(text):
    if type(text) is not str or len(text)>10000 or not re.fullmatch(r'(?:0|-?[1-9][0-9]*)(?:/[1-9][0-9]*)?',text):
        raise TypeCheckError('Malformed canonical rational')
    numerator,_,denominator=text.partition('/')
    n=_integer(numerator);d=_integer(denominator) if denominator else 1
    if denominator and (d==1 or math.gcd(n,d)!=1):raise TypeCheckError('Noncanonical rational')
    return n,d


def _proof(ast,depth=0,budget=None):
    budget=[12000] if budget is None else budget;budget[0]-=1
    if depth>200 or budget[0]<0 or type(ast) is not list or not ast or type(ast[0]) is not str:
        raise TypeCheckError('Malformed or oversized identity AST')
    def infer(child):return _proof(child,depth+1,budget)
    kind=ast[0]
    if kind=='n' and len(ast)==2:_rational(ast[1]);return RATIONAL
    if kind=='v' and len(ast)==2:_name(ast[1]);return RATIONAL
    if kind=='list' and len(ast)==2 and type(ast[1]) is list:
        children=[infer(child) for child in ast[1]]
        if not children or any(t!=children[0] for t in children):raise TypeCheckError('Irregular identity tensor')
        return NumericType((len(children),*children[0].shape))
    if kind=='un' and len(ast)==3 and ast[1]=='-':return infer_operation('neg',[infer(ast[2])])
    if kind=='bin' and len(ast)==4 and ast[1] in ('+','-','*','/','^','@'):
        operands=[infer(ast[2]),infer(ast[3])]
        if ast[1]=='^':
            exponent=ast[3]
            if exponent[0]=='n':n,d=_rational(exponent[1])
            elif exponent[0]=='un' and exponent[1]=='-' and exponent[2][0]=='n':
                n,d=_rational(exponent[2][1]);n=-n
            else:raise TypeCheckError('Identity exponent must be constant')
            if d!=1 or not 0<=n<=20:raise TypeCheckError('Identity exponent outside 0..20')
        return infer_operation(ast[1],operands)
    if kind=='call' and len(ast)==3 and ast[1] in ('relu','soma','dot','transposta') and type(ast[2]) is list:
        return infer_operation(ast[1],[infer(child) for child in ast[2]])
    raise TypeCheckError('Unknown identity AST form')


def validate_legacy(ir):
    """Validate the complete supported tensor/identity interchange schema."""
    _tree(ir)
    _fields(ir,('formato','versao','nos','simbolos','parametros','perdas','comandos'))
    if ir['formato']!='omega-ir-2' or ir['versao']!='1.0.0':raise TypeCheckError('Unsupported legacy IR version')
    shapes=certify_graph_shapes(ir)['nodes'];nodes=ir['nos'];parameter_nodes={}
    for i,node in enumerate(nodes):
        op=node['op'];extra=('v',) if op=='num' else ('nome',) if op=='param' else ()
        _fields(node,('op','args','forma',*extra))
        if op=='num':_rational(node['v'])
        if op=='param':
            name=_name(node['nome'])
            if name in parameter_nodes:raise TypeCheckError('Repeated parameter node')
            parameter_nodes[name]=i
        if op=='^':
            exponent=nodes[node['args'][1]]
            if exponent['op']!='num':raise TypeCheckError('Nonliteral exponent')
            n,d=_rational(exponent['v'])
            if d!=1 or not 0<=n<=20:raise TypeCheckError('Exponent outside 0..20')
    for table in ('simbolos','perdas'):
        if type(ir[table]) is not dict:raise TypeCheckError('Invalid IR name table')
        for name,index in ir[table].items():
            _name(name)
            if type(index) is not int or not 0<=index<len(nodes):raise TypeCheckError('Invalid IR table reference')
    symbols,losses=ir['simbolos'],ir['perdas']
    for name,index in losses.items():
        if symbols.get(name)!=index or shapes[index]['shape']:raise TypeCheckError('Loss table disagrees with symbols/types')
    parameters={}
    for p in ir['parametros']:
        _fields(p,('nome','id','inicial'));name=_name(p['nome'])
        if name in parameters or parameter_nodes.get(name)!=p['id'] or symbols.get(name)!=p['id']:
            raise TypeCheckError('Parameter table disagrees with nodes/symbols')
        if name in losses:raise TypeCheckError('Parameter cannot also be a loss')
        parameters[name]=p['id']
    if parameters!=parameter_nodes:raise TypeCheckError('Unbound parameter node')
    if type(ir['comandos']) is not list or len(ir['comandos'])>12000:raise TypeCheckError('Invalid IR commands')
    declared=set();theorems=set()
    for command in ir['comandos']:
        if type(command) is not dict or type(command.get('tipo')) is not str:raise TypeCheckError('Malformed IR command')
        kind=command['tipo'];name=command.get('nome')
        if kind=='provar':
            if name!='':raise TypeCheckError('Anonymous identity has a name')
        else:_name(name)
        fields=['tipo','nome']
        if kind=='declaracao':
            if name not in symbols or name in declared or name in theorems:raise TypeCheckError('Invalid declaration command')
            declared.add(name)
        elif kind in ('mostrar','mostrar_teorema','verificar'):
            if name not in (declared if kind=='mostrar' else theorems):raise TypeCheckError('Use before declaration')
        elif kind in ('gradiente','gradientes','passo','passo_livre','passo_ruidoso'):
            if name not in losses or name not in declared:raise TypeCheckError('Undeclared loss in command')
            if kind!='gradientes':
                fields.append('parametro');target=command.get('parametro')
                if type(target) is not str or target not in parameters or target not in declared:raise TypeCheckError('Undeclared parameter in command')
            if kind.startswith('passo'):
                fields.append('taxa');index=command.get('taxa')
                if type(index) is not int or not 0<=index<len(nodes) or shapes[index]['shape']:raise TypeCheckError('Invalid learning rate type')
            if kind=='passo_ruidoso':
                fields.append('semente');seed=command.get('semente')
                if type(seed) is not int or not 0<=seed<2**32:raise TypeCheckError('Invalid random seed')
        elif kind in ('provar','teorema','reescrever'):
            if kind=='reescrever':
                if name not in declared or name not in losses:raise TypeCheckError('Rewrite of unknown loss')
                if ('left' in command)!=('right' in command):raise TypeCheckError('Incomplete rewrite identity')
            if kind!='reescrever' or 'left' in command:
                fields.extend(('left','right'))
                if 'left' not in command or 'right' not in command:raise TypeCheckError('Missing identity operands')
                left,right=_proof(command['left']),_proof(command['right'])
                if left!=right or (kind=='reescrever' and not left.scalar):raise TypeCheckError('Identity operands have incompatible types')
            if kind=='teorema':
                if name in symbols or name in theorems:raise TypeCheckError('Redeclared theorem')
                theorems.add(name)
        else:raise TypeCheckError('Unknown IR command')
        _fields(command,fields)
    if declared!=set(symbols):raise TypeCheckError('Symbol table has no matching declarations')
    return shapes


def _encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise TypeCheckError('Duplicate JSON field')
        result[key]=value
    return result


def _constant(value):raise TypeCheckError('Nonfinite JSON number')


@dataclass(frozen=True)
class TypedIR:
    """Immutable validated bytes; exported dictionaries are independent copies."""
    _bytes: bytes

    def __post_init__(self):
        if type(self._bytes) is not bytes or len(self._bytes)>MAX_BYTES:raise TypeCheckError('IR byte budget exceeded')
        try:value=json.loads(self._bytes.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_constant)
        except (ValueError,UnicodeError,RecursionError) as exc:raise TypeCheckError('Malformed JSON IR') from exc
        _tree(value);_fields(value,('format','schema_version','dialect','graph','types'))
        if value['format']!=FORMAT or value['schema_version']!=VERSION or value['dialect']!='tensor':
            raise TypeCheckError('Unsupported typed IR version or dialect')
        types=validate_legacy(value['graph'])
        if type(value['types']) is not list or value['types']!=types:raise TypeCheckError('Typed IR annotations disagree with graph')
        if self._bytes!=_encode(value):raise TypeCheckError('IR serialization is not canonical')

    @classmethod
    def from_legacy(cls,graph):
        types=validate_legacy(graph)
        return cls(_encode({'format':FORMAT,'schema_version':VERSION,'dialect':'tensor','graph':graph,'types':types}))

    @classmethod
    def load(cls,path):
        with open(path,'rb') as stream:data=stream.read(MAX_BYTES+1)
        return cls(data)

    def to_bytes(self):return self._bytes
    def to_dict(self):return json.loads(self._bytes)
    def legacy(self):return self.to_dict()['graph']
    @property
    def sha256(self):return hashlib.sha256(self._bytes).hexdigest()
