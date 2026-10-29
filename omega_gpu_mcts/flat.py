"""Explicit host reference for the shared flat, index-only CUDA algorithms."""
from dataclasses import dataclass
from fractions import Fraction as Q
import ctypes as C
from omega_refine_check.syntax import parse,tree,identifier
from .numeric import Rational64
from .build import compile_host


class Shape(C.Structure):
    _fields_=[(name,C.c_uint32) for name in ('candidates','max_nodes','inputs','outputs','constants','examples','first','count')]


class RationalInterval(C.Structure):
    _fields_=[('lower',Rational64),('upper',Rational64)]
    @classmethod
    def from_pair(cls,pair):
        if type(pair) not in (list,tuple) or len(pair)!=2 or Q(pair[0])>Q(pair[1]):raise ValueError('Ordered rational interval required')
        return cls(Rational64.from_q(pair[0]),Rational64.from_q(pair[1]))


@dataclass
class FlatBatch:
    expressions:tuple
    variables:tuple
    constants:tuple
    max_nodes:int
    ops:object
    left:object
    right:object
    counts:object
    roots:object
    @classmethod
    def create(cls,expressions,variables):
        if not 1<=len(expressions)<=65536 or len(variables)>32:raise ValueError('Flat batch capacity exceeded')
        variables=tuple(identifier(x) for x in variables)
        if len(set(variables))!=len(variables):raise ValueError('Unique input names required')
        asts=tuple(parse(x) if type(x) is str else tree(x) for x in expressions);constant_pool=[];programs=[]
        for ast in asts:
            nodes=[]
            def emit(node):
                op=node[0]
                if op=='const':
                    q=str(Rational64.from_q(node[1]).fraction())
                    if q not in constant_pool:constant_pool.append(q)
                    record=(0,constant_pool.index(q),-1)
                elif op=='var':
                    if node[1] not in variables:raise ValueError('Out-of-scope flat AST input')
                    record=(1,variables.index(node[1]),-1)
                elif op in ('+','-','*','/','neg','relu'):
                    left=emit(node[1]);right=-1 if op in ('neg','relu') else emit(node[2])
                    record=({'+':2,'-':3,'*':4,'/':5,'neg':6,'relu':7}[op],left,right)
                else:raise ValueError('Only scalar rational grammar nodes can enter Tier-1')
                if len(nodes)>=4096:raise ValueError('Flat AST node budget exceeded')
                nodes.append(record);return len(nodes)-1
            root=emit(ast);programs.append((nodes,root))
        if len(constant_pool)>64:raise ValueError('Flat constant pool budget exceeded')
        width=max(len(p[0]) for p in programs);count=len(programs)
        if width*count>8*1024**2:raise ValueError('Flat tensor allocation budget exceeded')
        ops=(C.c_uint16*(width*count))();left=(C.c_int32*(width*count))();right=(C.c_int32*(width*count))()
        counts=(C.c_uint32*count)();roots=(C.c_uint32*count)()
        for candidate,(nodes,root) in enumerate(programs):
            counts[candidate]=len(nodes);roots[candidate]=root
            for i,(op,l,r) in enumerate(nodes):ops[i*count+candidate]=op;left[i*count+candidate]=l;right[i*count+candidate]=r
        return cls(asts,variables,tuple(constant_pool),width,ops,left,right,counts,roots)
    def shape(self,examples=1):return Shape(len(self.expressions),self.max_nodes,len(self.variables),1,len(self.constants),examples,0,len(self.expressions))
    def evaluate(self,examples):
        if not 1<=len(examples)<=64 or any(set(x)!=set(self.variables) for x in examples):raise ValueError('Bounded complete input examples required')
        library=C.CDLL(str(compile_host()));shape=self.shape(len(examples));jobs=shape.candidates*shape.examples
        inputs=(Rational64*(len(examples)*len(self.variables)))(*[Rational64.from_q(env[v]) for env in examples for v in self.variables])
        outputs=(Rational64*jobs)();scratch=(Rational64*(self.max_nodes*jobs))();errors=(C.c_uint8*jobs)()
        constants=(Rational64*len(self.constants))(*map(Rational64.from_q,self.constants))
        function=library.omega_host_evaluate
        function.argtypes=[C.POINTER(C.c_uint16),C.POINTER(C.c_int32),C.POINTER(C.c_int32),C.POINTER(Rational64),C.POINTER(Rational64),C.POINTER(Rational64),C.POINTER(Rational64),C.POINTER(C.c_uint32),C.POINTER(C.c_uint32),C.POINTER(C.c_uint8),Shape]
        if function(self.ops,self.left,self.right,inputs,outputs,scratch,constants,self.counts,self.roots,errors,shape):raise ValueError('Malformed host reference descriptor')
        return [{'values':[outputs[c*len(examples)+i].fraction() if not errors[c*len(examples)+i] else None for i in range(len(examples))],
                 'errors':list(errors[c*len(examples):(c+1)*len(examples)])} for c in range(len(self.expressions))]
    def filter(self,input_bounds,output_bounds):
        if len(input_bounds)!=len(self.variables):raise ValueError('Input interval shape mismatch')
        library=C.CDLL(str(compile_host()));shape=self.shape();count=shape.candidates
        inputs=(RationalInterval*len(input_bounds))(*map(RationalInterval.from_pair,input_bounds))
        limits=(RationalInterval*1)(RationalInterval.from_pair(output_bounds))
        scratch=(RationalInterval*(self.max_nodes*count))();constants=(Rational64*len(self.constants))(*map(Rational64.from_q,self.constants))
        mask=(C.c_uint8*count)();errors=(C.c_uint8*count)()
        f=library.omega_host_filter
        f.argtypes=[C.POINTER(C.c_uint16),C.POINTER(C.c_int32),C.POINTER(C.c_int32),C.POINTER(RationalInterval),C.POINTER(RationalInterval),C.POINTER(RationalInterval),C.POINTER(Rational64),C.POINTER(C.c_uint32),C.POINTER(C.c_uint32),C.POINTER(C.c_uint8),C.POINTER(C.c_uint8),Shape]
        if f(self.ops,self.left,self.right,inputs,limits,scratch,constants,self.counts,self.roots,mask,errors,shape):raise ValueError('Malformed interval reference descriptor')
        return {'backend':'host-reference','admissible':list(map(bool,mask)),'errors':list(errors),'formal_admission':False}
