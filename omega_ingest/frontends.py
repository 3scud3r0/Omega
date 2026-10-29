"""Data-only Python/C normalization. Candidate source is never imported/executed."""
import ast
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
from omega_refine_check.syntax import identifier
from omega_live.native import invoke


def bounded_source(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>1024**2:raise ValueError('Bounded regular foreign source required')
    return path.read_text()


class Flat:
    def __init__(self,parameters):
        if len(parameters)>16 or len(set(parameters))!=len(parameters):raise ValueError('Bounded distinct parameters required')
        self.parameters=[identifier(n) for n in parameters];self.nodes=[];self.bindings={}
        for i,name in enumerate(parameters):self.bindings[name]=self.add(1,-1,-1,i)
    def add(self,op,left=-1,right=-1,data=''):
        if len(self.nodes)>=63:raise ValueError('Lifted scalar AST exceeds 63 nodes')
        self.nodes.append([op,left,right,data]);return len(self.nodes)-1
    def const(self,value):
        q=Q(value)
        if max(abs(q.numerator).bit_length(),q.denominator.bit_length())>4096:raise ValueError('Foreign literal exceeds rational budget')
        return self.add(0,data=str(q))
    def finish(self,index):
        # Keep the chosen return as the final node without changing its value.
        if index!=len(self.nodes)-1:index=self.add(2,index,self.const(0))
        return self.nodes


def python_function(path,function,*,rational_reals=False):
    source=bounded_source(path);module=ast.parse(source)
    declarations=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name==function]
    if len(declarations)!=1:raise ValueError('One named Python function required')
    fn=declarations[0]
    if fn.decorator_list or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.defaults or fn.args.posonlyargs:raise ValueError('Fixed undecorated Python signature required')
    flat=Flat([a.arg for a in fn.args.args]);mode='rational-real' if rational_reals else 'python-integer'
    def expr(node):
        if isinstance(node,ast.Name):
            if node.id not in flat.bindings:raise ValueError('Unbound/global Python reference')
            return flat.bindings[node.id]
        if isinstance(node,ast.Constant):
            if type(node.value) is int:return flat.const(node.value)
            if type(node.value) is float and rational_reals:
                if not __import__('math').isfinite(node.value):raise ValueError('Nonfinite literal')
                return flat.const(Q.from_float(node.value)) # freeze actual Python binary64 constant
            raise ValueError('Python float literals require explicit rational-real reinterpretation')
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return flat.add(6,expr(node.operand))
        if isinstance(node,ast.BinOp):
            operators={ast.Add:2,ast.Sub:3,ast.Mult:4}
            if rational_reals:operators[ast.Div]=5
            if type(node.op) not in operators:raise ValueError('Python operator outside exact lifted numerical model')
            return flat.add(operators[type(node.op)],expr(node.left),expr(node.right))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='max' and len(node.args)==2 and not node.keywords and isinstance(node.args[0],ast.Constant) and type(node.args[0].value) is int and node.args[0].value==0:return flat.add(7,expr(node.args[1]))
        raise ValueError('Python effects, calls, control flow and dynamic shapes are outside this scalar lifter')
    result=None
    for statement in fn.body:
        if result is not None:raise ValueError('Unreachable Python statements are not silently discarded')
        if isinstance(statement,ast.Assign) and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name):flat.bindings[identifier(statement.targets[0].id)]=expr(statement.value)
        elif isinstance(statement,ast.Return):result=expr(statement.value)
        elif isinstance(statement,ast.Expr) and isinstance(statement.value,ast.Constant) and type(statement.value.value) is str:continue
        else:raise ValueError('Python function requires straight-line assignments and one return')
    if result is None:raise ValueError('Missing Python return')
    request=dict(name=identifier(function),parameters=flat.parameters,ast=flat.finish(result),semantics=mode)
    emitted=invoke('omega_ingest/py_ast_lifter.omega',request)
    return {**emitted,'origin':{'language':'python','sha256':hashlib.sha256(source.encode()).hexdigest(),'function':function},'formal_admission':False}


def c_function(path,function,*,rational_reals=False):
    from pycparser import c_parser,c_ast
    source=bounded_source(path)
    try:module=c_parser.CParser().parse('typedef int int32_t; typedef unsigned int uint32_t;\n'+source)
    except Exception as error:raise ValueError('C parser rejects unsupported preprocessing/includes or syntax: '+str(error)) from error
    matches=[n for n in module.ext if isinstance(n,c_ast.FuncDef) and n.decl.name==function]
    if len(matches)!=1:raise ValueError('One named C function required')
    fn=matches[0];decl=fn.decl.type
    def ctype(node):
        if not isinstance(node,c_ast.TypeDecl) or not isinstance(node.type,c_ast.IdentifierType):raise ValueError('C pointers, aggregates and function pointers need a verified memory model')
        words=node.type.names
        if words in (['int'],['signed','int'],['int32_t']):return 'c-int32'
        if words in (['unsigned'],['unsigned','int'],['uint32_t']):return 'c-uint32'
        if rational_reals and words in (['float'],['double']):return 'rational-real'
        raise ValueError('Unsupported C numeric type; floating point is never silently rationalized')
    mode=ctype(decl.type);params=decl.args.params if decl.args else []
    if len(params)==1 and isinstance(params[0],c_ast.Typename) and params[0].type.type.names==['void']:params=[]
    if any(not isinstance(p,c_ast.Decl) or ctype(p.type)!=mode for p in params):raise ValueError('Homogeneous explicit scalar C parameters required')
    flat=Flat([p.name for p in params])
    def expr(node):
        if isinstance(node,c_ast.ID):
            if node.name not in flat.bindings:raise ValueError('Unbound/global C name')
            return flat.bindings[node.name]
        if isinstance(node,c_ast.Constant):
            if node.type in ('int','unsigned int'):return flat.const(int(node.value.rstrip('uUlL'),0) if node.value.startswith(('0x','0X')) else int(node.value.rstrip('uUlL')))
            if rational_reals and node.type in ('float','double'):
                value=float(node.value.rstrip('fFlL'))
                if node.type=='float':value=__import__('struct').unpack('<f',__import__('struct').pack('<f',value))[0]
                return flat.const(Q.from_float(value))
            raise ValueError('Unsupported C constant')
        if isinstance(node,c_ast.UnaryOp) and node.op=='-':return flat.add(6,expr(node.expr))
        if isinstance(node,c_ast.BinaryOp) and node.op in ('+','-','*','/'):return flat.add({'+':2,'-':3,'*':4,'/':5}[node.op],expr(node.left),expr(node.right))
        raise ValueError('C effects/control/pointer operation is outside admitted lifter')
    result=None
    for statement in fn.body.block_items or []:
        if result is not None:raise ValueError('Unreachable C statements are not silently dropped')
        if isinstance(statement,c_ast.Decl):
            if ctype(statement.type)!=mode or statement.init is None:raise ValueError('Initialized homogeneous C local required')
            flat.bindings[identifier(statement.name)]=expr(statement.init)
        elif isinstance(statement,c_ast.Assignment) and statement.op=='=' and isinstance(statement.lvalue,c_ast.ID):
            if statement.lvalue.name not in flat.bindings:raise ValueError('C assignment to unknown local')
            flat.bindings[statement.lvalue.name]=expr(statement.rvalue)
        elif isinstance(statement,c_ast.Return):result=expr(statement.expr)
        else:raise ValueError('C function must be straight-line scalar arithmetic')
    if result is None:raise ValueError('Missing C return')
    emitted=invoke('omega_ingest/c_ast_lifter.omega',dict(name=identifier(function),parameters=flat.parameters,ast=flat.finish(result),semantics=mode))
    return {**emitted,'origin':{'language':'c','sha256':hashlib.sha256(source.encode()).hexdigest(),'function':function},'formal_admission':False,'undefined_signed_overflow':'traps instead of inventing C behavior'}


def wasm_function(path,function,*,name='lifted'):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>1024**2:raise ValueError('Bounded regular WASM required')
    raw=path.read_bytes()
    import wasmtime
    wasmtime.Module.validate(wasmtime.Engine(),raw)
    emitted=invoke('omega_ingest/wasm_lifter.omega',{'bytes':list(raw),'export':function,'name':identifier(name)})
    return {**emitted,'origin':{'language':'wasm','sha256':hashlib.sha256(raw).hexdigest(),'export':function},'formal_admission':False}


def save(result,directory):
    from omega_live.context import checkpoint,emit
    checkpoint('ingest.write',{'origin':result.get('origin',{}),'formal_admission':False})
    root=Path(directory);root.mkdir(parents=True,exist_ok=False)
    (root/'lifted.omega').write_text(result['source']);(root/'lift.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    emit('ingest.source-emitted',{'source_sha256':hashlib.sha256(result['source'].encode()).hexdigest(),'path':str(root/'lifted.omega'),'formal_admission':False})
    return {'directory':str(root),'source':str(root/'lifted.omega'),'report':result}
