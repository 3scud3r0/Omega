"""Checkable dimension contracts, including symbolic dimension equalities.

Symbols stand for positive bounded integers, never arbitrary expressions. A
contract is only executable after all symbols have concrete bindings.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .typesystem import NumericType, TypeCheckError


def _shape(shape):
    if type(shape) is not tuple or len(shape)>2:
        raise TypeCheckError('A shape must be a tuple of rank at most two')
    for d in shape:
        if type(d) is int and 1<=d<=2048:continue
        if type(d) is str and d.isidentifier() and len(d)<=64:continue
        raise TypeCheckError('Invalid concrete or symbolic dimension')
    if all(type(d) is int for d in shape):NumericType(shape)
    return shape


class _Equalities:
    def __init__(self):self.parent={}
    def root(self,d):
        trail=[]
        while d in self.parent:trail.append(d);d=self.parent[d]
        for previous in trail:self.parent[previous]=d
        return d
    def equal(self,a,b):
        a,b=self.root(a),self.root(b)
        if a==b:return
        if type(a) is int and type(b) is int:
            raise TypeCheckError(f'Incompatible dimensions: {a} and {b}')
        if type(a) is int or (type(b) is str and b<a):a,b=b,a
        self.parent[a]=b


@dataclass(frozen=True)
class DimensionContract:
    operator: str
    inputs: tuple[tuple[int|str,...],...]
    output: tuple[int|str,...]
    equalities: tuple[tuple[int|str,int|str],...]

    def specialize(self,bindings):
        if type(bindings) is not dict:raise TypeCheckError('Dimension bindings must be a dictionary')
        symbols={d for shape in self.inputs for d in shape if type(d) is str}
        if set(bindings)!=symbols:raise TypeCheckError('Missing or unexpected dimension bindings')
        eq=_Equalities()
        for a,b in self.equalities:eq.equal(a,b)
        for name,value in sorted(bindings.items()):
            if type(value) is not int or not 1<=value<=2048:raise TypeCheckError('Invalid dimension binding')
            eq.equal(name,value)
        inputs=tuple(NumericType(tuple(eq.root(d) for d in shape)) for shape in self.inputs)
        result=NumericType(tuple(eq.root(d) for d in self.output))
        # Reconstruct the rule; callers cannot forge an output on a dataclass.
        checked=dimension_contract(self.operator,tuple(t.shape for t in inputs))
        if checked.output!=result.shape:raise TypeCheckError('Forged dimension contract')
        return result

    def to_dict(self):
        return {'format':'omega-dimensions-1','operator':self.operator,
                'inputs':[list(s) for s in self.inputs],'output':list(self.output),
                'equalities':[list(e) for e in self.equalities]}

    @classmethod
    def from_dict(cls,value):
        if type(value) is not dict or set(value)!={'format','operator','inputs','output','equalities'}:
            raise TypeCheckError('Malformed dimension contract')
        if value['format']!='omega-dimensions-1' or type(value['inputs']) is not list:
            raise TypeCheckError('Unsupported dimension contract')
        if any(type(s) is not list for s in value['inputs']):raise TypeCheckError('Malformed input shapes')
        if type(value['output']) is not list or type(value['equalities']) is not list:
            raise TypeCheckError('Malformed dimension obligations')
        _shape(tuple(value['output']))
        for pair in value['equalities']:
            if type(pair) is not list or len(pair)!=2:raise TypeCheckError('Malformed dimension equality')
            for dimension in pair:_shape((dimension,))
        result=dimension_contract(value['operator'],tuple(tuple(s) for s in value['inputs']))
        if result.to_dict()!=value:raise TypeCheckError('Noncanonical or forged dimension contract')
        return result


def dimension_contract(operator,inputs):
    arity={'neg':1,'relu':1,'soma':1,'transposta':1,'+':2,'-':2,'*':2,'/':2,'^':2,'@':2,'dot':2}
    if type(operator) is not str or operator not in arity or type(inputs) is not tuple or len(inputs)!=arity[operator]:
        raise TypeCheckError('Unknown dimension rule or incorrect arity')
    inputs=tuple(_shape(s) for s in inputs);a=inputs[0];b=inputs[1] if len(inputs)>1 else ()
    equations=[];eq=_Equalities()
    def equal(x,y):
        if x!=y:equations.append((x,y));eq.equal(x,y)
    def same(x,y):
        if len(x)!=len(y):raise TypeCheckError('Incompatible tensor ranks')
        for left,right in zip(x,y):equal(left,right)
    if operator in ('neg','relu'):out=a
    elif operator in ('+','-'):same(a,b);out=a
    elif operator=='*':
        if a and b:raise TypeCheckError('Scalar multiplication requires a scalar')
        out=a or b
    elif operator=='/':
        if b:raise TypeCheckError('A denominator must be scalar')
        out=a
    elif operator=='^':
        if a or b:raise TypeCheckError('Power requires scalars')
        out=()
    elif operator=='@':
        if len(a)!=2 or len(b) not in (1,2):raise TypeCheckError('Matrix product requires matrix/vector operands')
        equal(a[1],b[0]);out=(a[0],) if len(b)==1 else (a[0],b[1])
    elif operator=='dot':
        if len(a)!=1:raise TypeCheckError('Dot product requires vectors')
        same(a,b);out=()
    elif operator=='transposta':
        if len(a)!=2:raise TypeCheckError('Transpose requires a matrix')
        out=a[::-1]
    else:out=()
    out=_shape(tuple(eq.root(d) for d in out))
    return DimensionContract(operator,inputs,out,tuple(equations))


def certify_graph_shapes(ir):
    """Check every legacy graph node, not just publicly named values.

    The digest binds shape-relevant data only. This is a shape certificate,
    not a certificate for values, commands, code generation or differentiation.
    """
    if type(ir) is not dict or type(ir.get('nos')) is not list or len(ir['nos'])>12000:
        raise TypeCheckError('Invalid tensor graph')
    types=[];records=[]
    for i,node in enumerate(ir['nos']):
        if type(node) is not dict or type(node.get('op')) is not str or type(node.get('args')) is not list or type(node.get('forma')) is not list:
            raise TypeCheckError('Malformed tensor node')
        op,args=node['op'],node['args'];declared=NumericType(tuple(node['forma']))
        if any(type(j) is not int or not 0<=j<i for j in args):raise TypeCheckError('Invalid dimension dependency')
        shapes=tuple(types[j].shape for j in args)
        if op in ('num','param','zeros','identidade'):
            if args:raise TypeCheckError('Unexpected constructor arguments')
            if op=='num' and declared.shape:raise TypeCheckError('A number is scalar')
            if op=='zeros' and not declared.shape:raise TypeCheckError('Zeros requires a tensor')
            if op=='identidade' and (len(declared.shape)!=2 or declared.shape[0]!=declared.shape[1]):
                raise TypeCheckError('Identity requires a square matrix')
            inferred=declared
        elif op=='stack':
            if not args or any(s!=shapes[0] for s in shapes):raise TypeCheckError('Irregular stack')
            inferred=NumericType((len(args),*shapes[0]))
        else:inferred=dimension_contract(op,shapes).specialize({})
        if inferred!=declared:raise TypeCheckError(f'Forged output dimensions at node {i}')
        types.append(inferred);records.append({'op':op,'args':args,'shape':list(declared.shape)})
    params=ir.get('parametros')
    if type(params) is not list:raise TypeCheckError('Missing parameter dimensions')
    links=[]
    for p in params:
        if type(p) is not dict or any(type(p.get(k)) is not int for k in ('id','inicial')):
            raise TypeCheckError('Invalid parameter dimension link')
        i,j=p['id'],p['inicial']
        if not 0<=j<i<len(types) or records[i]['op']!='param' or types[i]!=types[j]:
            raise TypeCheckError('Parameter/initializer dimensions disagree')
        links.append([i,j])
    payload={'nodes':records,'parameters':links}
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'format':'omega-graph-shapes-1','shape_graph_sha256':digest,'nodes':[t.to_dict() for t in types]}


def verify_graph_shapes(ir,certificate):
    if type(certificate) is not dict:raise TypeCheckError('Malformed shape certificate')
    try:
        expected=json.dumps(certify_graph_shapes(ir),sort_keys=True,separators=(',',':'),allow_nan=False)
        actual=json.dumps(certificate,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (ValueError,TypeError,RecursionError):raise TypeCheckError('Malformed shape certificate') from None
    if expected!=actual:
        raise TypeCheckError('Shape certificate does not match its graph')
    return True
