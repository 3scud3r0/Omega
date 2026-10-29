"""Bounded ONNX protobuf/SafeTensors readers and static rational graph lifting.

No pickle, Python imports from a model, external tensor files or runtime Torch.
Stored finite floats become their exact binary rationals; operation rounding is
explicitly reinterpreted, never mislabelled IEEE semantic equivalence.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
import itertools
import json
from math import prod,isfinite
from pathlib import Path
import struct
from omega.certified_graph import validate,omega_source

MAX=64*1024**2


def read(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX:raise ValueError('Bounded regular tensor/model file required')
    return path.read_bytes()


def varint(data,at):
    value=0
    for i in range(10):
        if at>=len(data):raise ValueError('Truncated protobuf integer')
        byte=data[at];at+=1;value|=(byte&127)<<(7*i)
        if byte<128:
            if value>=2**64:raise ValueError('Protobuf integer overflow')
            return value,at
    raise ValueError('Overlong protobuf integer')


def fields(data):
    out={};at=0;count=0
    while at<len(data):
        tag,at=varint(data,at);number,wire=tag>>3,tag&7
        if not number:raise ValueError('Zero protobuf field')
        if wire==0:value,at=varint(data,at)
        elif wire in (1,5):
            n=8 if wire==1 else 4
            if at+n>len(data):raise ValueError('Truncated protobuf scalar')
            value=data[at:at+n];at+=n
        elif wire==2:
            n,at=varint(data,at)
            if n>MAX or at+n>len(data):raise ValueError('Truncated/oversized protobuf field')
            value=data[at:at+n];at+=n
        else:raise ValueError('Unsupported protobuf wire encoding')
        out.setdefault(number,[]).append((wire,value));count+=1
        if count>100000:raise ValueError('Protobuf field budget')
    return out


def one(f,key,default=None):
    values=f.get(key,[])
    if len(values)>1:raise ValueError('Duplicate singular protobuf field')
    return values[0][1] if values else default

def text(f,key,default=''):return one(f,key,default.encode()).decode('utf-8')
def ints(f,key):
    result=[]
    for wire,value in f.get(key,[]):
        if wire==0:result.append(value)
        elif wire==2:
            at=0
            while at<len(value):n,at=varint(value,at);result.append(n)
        else:raise ValueError('Invalid packed integers')
    return result


def numeric(raw,dtype,count):
    formats={'F64':('d',8),'F32':('f',4),'F16':('e',2),'I64':('q',8),'I32':('i',4),'I16':('h',2),'I8':('b',1),'U8':('B',1),'U32':('I',4),'U64':('Q',8)}
    if dtype=='BF16':
        if len(raw)!=2*count:raise ValueError('BFloat16 tensor length')
        values=[struct.unpack('<f',b'\x00\x00'+raw[i:i+2])[0] for i in range(0,len(raw),2)]
    else:
        if dtype not in formats:raise ValueError('Unsupported numeric tensor dtype')
        fmt,size=formats[dtype]
        if len(raw)!=size*count:raise ValueError('Tensor byte length mismatch')
        values=struct.unpack('<'+str(count)+fmt,raw)
    if any(type(x) is float and not isfinite(x) for x in values):raise ValueError('NaN/Infinity require an explicit separate semantic model')
    return tuple(Q.from_float(x) if type(x) is float else Q(x) for x in values)


@dataclass(frozen=True)
class Ref:
    index:int
@dataclass(frozen=True)
class Tensor:
    shape:tuple
    values:tuple
    def __post_init__(self):
        if len(self.shape)>4 or any(type(d) is not int or not 1<=d<=4096 for d in self.shape) or prod(self.shape)>4096 or len(self.values)!=prod(self.shape):raise ValueError('Static tensor shape/element budget')
    def at(self,index):
        if len(index)!=len(self.shape):raise ValueError('Tensor coordinate rank')
        n=0
        for i,d in zip(index,self.shape):
            if not 0<=i<d:raise ValueError('Tensor index outside static shape')
            n=n*d+i
        return self.values[n]


def safetensors(path):
    data=read(path)
    if len(data)<8:raise ValueError('Truncated SafeTensors')
    n=int.from_bytes(data[:8],'little')
    if n>1024**2 or 8+n>len(data):raise ValueError('SafeTensors header budget')
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError('Duplicate SafeTensors key')
            d[k]=v
        return d
    header=json.loads(data[8:8+n],object_pairs_hook=unique);payload=data[8+n:];out={};ranges=[]
    for name,entry in header.items():
        if name=='__metadata__':continue
        if set(entry)!={'dtype','shape','data_offsets'}:raise ValueError('Unknown tensor fields')
        start,end=entry['data_offsets']
        if type(start) is not int or type(end) is not int or not 0<=start<=end<=len(payload):raise ValueError('Tensor offset bounds')
        ranges.append((start,end));shape=tuple(entry['shape']);count=prod(shape)
        if count>4096:raise ValueError('Tensor element budget')
        out[name]=Tensor(shape,numeric(payload[start:end],entry['dtype'],count))
    ordered=sorted(ranges);end=0
    for lo,hi in ordered:
        if lo!=end:raise ValueError('Overlapping or unaccounted SafeTensors bytes')
        end=hi
    if end!=len(payload):raise ValueError('Trailing SafeTensors payload')
    return out


def onnx_tensor(raw):
    f=fields(raw)
    if 13 in f or one(f,14,0)!=0:raise ValueError('External ONNX tensor data is not permitted')
    shape=tuple(ints(f,1));count=prod(shape)
    if count>4096:raise ValueError('Tensor element budget')
    dtype=one(f,2);formats={1:'F32',11:'F64',10:'F16',16:'BF16',7:'I64',6:'I32',5:'I16',3:'I8',2:'U8',12:'U32',13:'U64'}
    if dtype not in formats:raise ValueError('Unsupported ONNX dtype')
    raw_data=one(f,9)
    if raw_data is None:
        if dtype in (1,11):
            field=4 if dtype==1 else 10;raw_data=b''.join(v for w,v in f.get(field,[]) if w in (1,2,5))
        else:
            field=7 if dtype==7 else 11 if dtype in (12,13) else 5;values=ints(f,field)
            code,size={'I64':('q',8),'I32':('i',4),'I16':('h',2),'I8':('b',1),'U8':('B',1),'U32':('I',4),'U64':('Q',8),'F16':('H',2),'BF16':('H',2)}[formats[dtype]]
            mask=2**(size*8)-1;values=[v&mask for v in values]
            if code in ('q','i','h','b'):values=[v-2**(size*8) if v>=2**(size*8-1) else v for v in values]
            raw_data=struct.pack('<'+str(len(values))+code,*values)
    return text(f,8),Tensor(shape,numeric(raw_data,formats[dtype],count))


def coordinates(shape):return itertools.product(*(range(d) for d in shape))
def broadcast_shape(a,b):
    n=max(len(a),len(b));aa=(1,)*(n-len(a))+a;bb=(1,)*(n-len(b))+b
    if any(x!=y and x!=1 and y!=1 for x,y in zip(aa,bb)):raise ValueError('Static broadcasting mismatch')
    return tuple(max(x,y) for x,y in zip(aa,bb))
def broadcast_at(t,index):return t.at(tuple(0 if d==1 else i for d,i in zip(t.shape,index[len(index)-len(t.shape):])))


class Graph:
    def __init__(self):self.nodes=[];self.inputs=0
    def node(self,op,**data):
        if len(self.nodes)>=4096:raise ValueError('Rational graph node budget')
        self.nodes.append({'op':op,**data});return Ref(self.inputs+len(self.nodes)-1)
    def affine(self,terms,bias=Q(0)):
        combined={}
        for value,coefficient in terms:
            if isinstance(value,Ref):combined[value.index]=combined.get(value.index,Q(0))+coefficient
            else:bias+=value*coefficient
        if not combined:return bias
        return self.node('affine',terms=[[i,str(w)] for i,w in sorted(combined.items()) if w],bias=str(bias))
    def binary(self,op,a,b):
        if op in ('Add','Sub'):return self.affine([(a,Q(1)),(b,Q(1) if op=='Add' else Q(-1))])
        if op=='Mul':
            if not isinstance(a,Ref):return self.affine([(b,a)])
            if not isinstance(b,Ref):return self.affine([(a,b)])
        if op=='Div' and not isinstance(b,Ref):
            if not b:raise ValueError('Constant division by zero')
            return self.affine([(a,1/b)])
        if not isinstance(a,Ref) and not isinstance(b,Ref):return a*b if op=='Mul' else a/b
        def ref(x):return x if isinstance(x,Ref) else self.node('affine',terms=[],bias=str(x))
        return self.node('mul' if op=='Mul' else 'div',left=ref(a).index,right=ref(b).index)
    def unary(self,op,x):
        if op=='relu' and not isinstance(x,Ref):return max(Q(0),x)
        if not isinstance(x,Ref):x=self.node('affine',terms=[],bias=str(x))
        return self.node(op,input=x.index)
    def elementwise(self,op,a,b):
        shape=broadcast_shape(a.shape,b.shape)
        return Tensor(shape,tuple(self.binary(op,broadcast_at(a,index),broadcast_at(b,index)) for index in coordinates(shape)))
    def matmul(self,a,b):
        if len(a.shape)<2 or len(b.shape)<2 or a.shape[-1]!=b.shape[-2]:raise ValueError('MatMul requires compatible static matrix dimensions')
        batch=broadcast_shape(a.shape[:-2],b.shape[:-2]);shape=batch+(a.shape[-2],b.shape[-1]);values=[]
        for index in coordinates(shape):
            batch_index=index[:-2];row,col=index[-2:];total=Q(0)
            ai=tuple(0 if d==1 else k for d,k in zip(a.shape[:-2],batch_index[len(batch_index)-len(a.shape[:-2]):]));bi=tuple(0 if d==1 else k for d,k in zip(b.shape[:-2],batch_index[len(batch_index)-len(b.shape[:-2]):]))
            for k in range(a.shape[-1]):total=self.binary('Add',total,self.binary('Mul',a.at(ai+(row,k)),b.at(bi+(k,col))))
            values.append(total)
        return Tensor(shape,tuple(values))


def onnx(path,*,allow_approx=False,precision_bits=32):
    raw=read(path);model=fields(raw);graph_data=one(model,7)
    if graph_data is None:raise ValueError('ONNX graph absent')
    graph_proto=fields(graph_data);tensors={};builder=Graph()
    for _,value in graph_proto.get(5,[]):
        name,tensor=onnx_tensor(value)
        if not name or name in tensors:raise ValueError('Duplicate initializer')
        tensors[name]=tensor
    inputs=[]
    for _,value in graph_proto.get(11,[]):
        info=fields(value);name=text(info,1)
        if name in tensors:continue
        tensor_type=fields(one(fields(one(info,2,b'')),1,b''));shape_data=fields(one(tensor_type,2,b''));shape=[]
        for _,dim in shape_data.get(1,[]):
            fields_dim=fields(dim);size=one(fields_dim,1)
            if size is None or one(fields_dim,2) is not None:raise ValueError('Dynamic ONNX dimensions require an explicit bounded specialization')
            shape.append(size)
        if not shape or builder.inputs+prod(shape)>256:raise ValueError('Input shape budget')
        refs=tuple(Ref(builder.inputs+i) for i in range(prod(shape)));builder.inputs+=len(refs);tensors[name]=Tensor(tuple(shape),refs);inputs.append({'name':name,'shape':shape})
    if not builder.inputs:raise ValueError('At least one static input required')
    def transpose(t,perm=None):
        perm=tuple(reversed(range(len(t.shape)))) if perm is None else tuple(perm)
        if sorted(perm)!=list(range(len(t.shape))):raise ValueError('Transpose permutation')
        shape=tuple(t.shape[i] for i in perm);values=[]
        for index in coordinates(shape):
            original=[0]*len(perm)
            for i,p in enumerate(perm):original[p]=index[i]
            values.append(t.at(tuple(original)))
        return Tensor(shape,tuple(values))
    for _,raw_node in graph_proto.get(1,[]):
        node=fields(raw_node);op=text(node,4);domain=text(node,7)
        if domain not in ('','ai.onnx'):raise ValueError('Custom ONNX operator domains are not implicitly trusted')
        names=[v.decode() for _,v in node.get(1,[])];outputs=[v.decode() for _,v in node.get(2,[])];attributes={}
        for _,value in node.get(5,[]):
            attr=fields(value);name=text(attr,1)
            if name in attributes:raise ValueError('Duplicate ONNX attribute')
            attributes[name]=attr
        args=[tensors[n] for n in names if n]
        if op in ('Add','Sub','Mul','Div') and len(args)==2:value=builder.elementwise(op,*args)
        elif op=='MatMul' and len(args)==2:value=builder.matmul(*args)
        elif op=='Gemm' and len(args) in (2,3):
            a,b=args[:2]
            if one(attributes.get('transA',{}),3,0):a=transpose(a)
            if one(attributes.get('transB',{}),3,0):b=transpose(b)
            alpha=Q.from_float(struct.unpack('<f',one(attributes.get('alpha',{}),2,struct.pack('<f',1)))[0]);beta=Q.from_float(struct.unpack('<f',one(attributes.get('beta',{}),2,struct.pack('<f',1)))[0])
            value=builder.matmul(a,b)
            if alpha!=1:value=builder.elementwise('Mul',value,Tensor((),(alpha,)))
            if len(args)==3:value=builder.elementwise('Add',value,builder.elementwise('Mul',args[2],Tensor((),(beta,))))
        elif op=='Relu' and len(args)==1:value=Tensor(args[0].shape,tuple(builder.unary('relu',x) for x in args[0].values))
        elif op=='Identity' and len(args)==1:value=args[0]
        elif op=='Transpose' and len(args)==1:value=transpose(args[0],ints(attributes['perm'],8) if 'perm' in attributes else None)
        elif op=='Reshape' and len(args)==2:
            if any(isinstance(x,Ref) or x.denominator!=1 for x in args[1].values):raise ValueError('Reshape dimensions must be constant integers')
            shape=tuple(int(x) for x in args[1].values)
            if prod(shape)!=len(args[0].values):raise ValueError('Explicit positive static Reshape required')
            value=Tensor(shape,args[0].values)
        elif op=='Constant' and not args and 'value' in attributes:_,value=onnx_tensor(one(attributes['value'],5))
        elif op in ('Exp','Sqrt','Softmax') and len(args)==1:
            if not allow_approx:raise ValueError('Transcendental ONNX graph requires explicit certified approximation opt-in')
            t=args[0]
            if op=='Exp':value=Tensor(t.shape,tuple(builder.unary('exp',x) for x in t.values))
            elif op=='Sqrt':value=Tensor(t.shape,tuple(builder.binary('Div',Q(1),builder.unary('rsqrt',x)) for x in t.values))
            else:
                axis=one(attributes.get('axis',{}),3,2**64-1);axis=axis-2**64 if axis>=2**63 else axis
                if axis not in (-1,len(t.shape)-1):raise ValueError('Softmax currently supports the last static axis')
                data=[];width=t.shape[-1]
                for first in range(0,len(t.values),width):
                    e=[builder.unary('exp',x) for x in t.values[first:first+width]];den=builder.affine([(x,Q(1)) for x in e]);data.extend(builder.binary('Div',x,den) for x in e)
                value=Tensor(t.shape,tuple(data))
        else:raise ValueError('Unsupported ONNX operator: '+op)
        if len(outputs)!=1 or outputs[0] in tensors:raise ValueError('Distinct single-output ONNX nodes required')
        tensors[outputs[0]]=value
    output_refs=[];output_info=[]
    for _,raw_output in graph_proto.get(12,[]):
        name=text(fields(raw_output),1)
        if name not in tensors:raise ValueError('Unbound ONNX output')
        t=tensors[name];output_info.append({'name':name,'shape':list(t.shape)})
        for x in t.values:output_refs.append(x.index if isinstance(x,Ref) else builder.node('affine',terms=[],bias=str(x)).index)
    graph={'inputs':builder.inputs,'nodes':builder.nodes,'outputs':output_refs}
    if allow_approx:graph['precision_bits']=precision_bits
    validate(graph)
    from omega_live.native import invoke
    if any(n['op'] in ('exp','rsqrt') for n in graph['nodes']):source=omega_source(graph,[Q(0)]*graph['inputs'])
    else:source=invoke('omega_ingest/onnx_lifter.omega',{'graph':graph})['source']
    return {'source':source,'graph':graph,'inputs':inputs,'outputs':output_info,'origin':{'sha256':hashlib.sha256(raw).hexdigest(),'language':'onnx'},'numerical_model':'exact rational reinterpretation of stored finite floats; certified approximations require domain/error proofs','formal_admission':False}
