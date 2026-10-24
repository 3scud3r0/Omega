"""Typed SSA graph analysis with edge-aware phi uses and dominators.

The tensor adapter represents one pure graph evaluation, not the whole mutable
training-command stream. This module does not rewrite executable programs.
"""
from __future__ import annotations

from dataclasses import dataclass
from .typesystem import NumericType,TypeCheckError,infer_operation
from .typed_ir import TypedIR,_rational,_encode


@dataclass(frozen=True)
class Value:
    name: str
    operator: str
    arguments: tuple[str,...]
    annotation: NumericType
    incoming: tuple[tuple[str,str],...]=()
    literal: str|None=None


@dataclass(frozen=True)
class Terminator:
    kind: str
    targets: tuple[str,...]=()
    operands: tuple[str,...]=()


@dataclass(frozen=True)
class Block:
    name: str
    values: tuple[Value,...]
    terminator: Terminator


@dataclass(frozen=True)
class Graph:
    entry: str
    blocks: tuple[Block,...]


def _identifier(name):
    if type(name) is not str or not name.isidentifier() or len(name)>256:raise TypeCheckError('Invalid SSA name')


def analyze(graph):
    if type(graph) is not Graph or type(graph.blocks) is not tuple or not 1<=len(graph.blocks)<=256:
        raise TypeCheckError('SSA block budget exceeded')
    _identifier(graph.entry)
    blocks={};definitions={};total=0;references=0
    for block in graph.blocks:
        if type(block) is not Block:raise TypeCheckError('Malformed SSA block')
        _identifier(block.name)
        if block.name in blocks:raise TypeCheckError('Repeated SSA block')
        if type(block.values) is not tuple:raise TypeCheckError('SSA values must be immutable')
        blocks[block.name]=block;total+=len(block.values)
        if total>12000:raise TypeCheckError('SSA definition budget exceeded')
        ordinary=False
        for index,value in enumerate(block.values):
            if type(value) is not Value:raise TypeCheckError('Malformed SSA definition')
            _identifier(value.name)
            if value.name in definitions:raise TypeCheckError('SSA value has multiple definitions')
            if type(value.annotation) is not NumericType or type(value.operator) is not str:
                raise TypeCheckError('Missing SSA type/operator')
            if type(value.arguments) is not tuple or type(value.incoming) is not tuple:raise TypeCheckError('Malformed SSA operands')
            if len(value.arguments)>2048 or len(value.incoming)>256:raise TypeCheckError('SSA operand budget exceeded')
            references+=len(value.arguments)+len(value.incoming)
            if references>120000:raise TypeCheckError('SSA reference budget exceeded')
            for name in value.arguments:_identifier(name)
            for edge in value.incoming:
                if type(edge) is not tuple or len(edge)!=2:raise TypeCheckError('Malformed phi edge')
                for name in edge:_identifier(name)
            if value.operator=='phi':
                if ordinary or value.arguments or value.literal is not None:raise TypeCheckError('Phi must precede ordinary definitions')
            else:
                ordinary=True
                if value.incoming:raise TypeCheckError('Only phi may have edge operands')
                if value.operator!='num' and value.literal is not None:raise TypeCheckError('Unexpected SSA literal')
            definitions[value.name]=(block.name,index,value)
    if graph.entry not in blocks:raise TypeCheckError('Missing SSA entry block')
    successors={};predecessors={name:set() for name in blocks}
    for name,block in blocks.items():
        term=block.terminator
        if type(term) is not Terminator or type(term.targets) is not tuple or type(term.operands) is not tuple:
            raise TypeCheckError('Malformed SSA terminator')
        expected={'jump':(1,0),'branch':(2,1),'return':(0,None)}
        if type(term.kind) is not str or term.kind not in expected:raise TypeCheckError('Unknown SSA terminator')
        targets,operands=expected[term.kind]
        if len(term.targets)!=targets or (operands is not None and len(term.operands)!=operands) or len(term.operands)>12000:
            raise TypeCheckError('SSA terminator arity mismatch')
        references+=len(term.operands)
        if references>120000:raise TypeCheckError('SSA reference budget exceeded')
        for ref in (*term.targets,*term.operands):_identifier(ref)
        if len(set(term.targets))!=len(term.targets) or any(t not in blocks for t in term.targets):
            raise TypeCheckError('Duplicate or missing control-flow successor')
        successors[name]=term.targets
        for target in term.targets:predecessors[target].add(name)
    if predecessors[graph.entry]:raise TypeCheckError('Entry block cannot have predecessors')
    reachable=set();pending=[graph.entry]
    while pending:
        name=pending.pop()
        if name in reachable:continue
        reachable.add(name);pending.extend(successors[name])
    if reachable!=set(blocks):raise TypeCheckError('Unreachable SSA blocks')
    names=sorted(blocks);bits={name:1<<i for i,name in enumerate(names)};all_bits=(1<<len(names))-1
    dominators={name:bits[name] if name==graph.entry else all_bits for name in names}
    changed=True
    while changed:
        changed=False
        for name in names:
            if name==graph.entry:continue
            common=all_bits
            for predecessor in predecessors[name]:common &= dominators[predecessor]
            result=common|bits[name]
            if result!=dominators[name]:dominators[name]=result;changed=True
    def dominates(a,b):return bool(dominators[b]&bits[a])
    immediate={graph.entry:None}
    for name in names:
        if name==graph.entry:continue
        strict=[d for d in names if d!=name and dominates(d,name)]
        immediate[name]=max(strict,key=lambda d:dominators[d].bit_count())
    frontiers={name:set() for name in names}
    for name in names:
        if len(predecessors[name])<2:continue
        for predecessor in sorted(predecessors[name]):
            runner=predecessor
            while runner!=immediate[name]:
                frontiers[runner].add(name);runner=immediate[runner]
                if runner is None:break
    uses={name:[] for name in definitions}
    def use(ref,block,index,position,edge=None):
        if ref not in definitions:raise TypeCheckError('Undefined SSA operand: '+ref)
        owner,offset,value=definitions[ref];target=edge or block
        if not dominates(owner,target) or (edge is None and owner==block and offset>=index):
            raise TypeCheckError('SSA definition does not dominate use: '+ref)
        uses[ref].append({'block':block,'index':index,'operand':position,'edge':edge})
        return value.annotation
    for name in names:
        block=blocks[name]
        for index,value in enumerate(block.values):
            op=value.operator;annotation=value.annotation
            if op=='phi':
                if {p for p,_ in value.incoming}!=predecessors[name] or len(value.incoming)!=len(predecessors[name]) or not value.incoming:
                    raise TypeCheckError('Phi must have exactly one operand for every predecessor')
                for position,(edge,ref) in enumerate(value.incoming):
                    if use(ref,name,index,position,edge)!=annotation:raise TypeCheckError('Phi operand type mismatch')
            else:
                types=[use(ref,name,index,j) for j,ref in enumerate(value.arguments)]
                if op=='input':
                    if name!=graph.entry or types:raise TypeCheckError('Inputs belong in entry without operands')
                    inferred=annotation
                elif op=='num':
                    if types:raise TypeCheckError('Literal has operands')
                    _rational(value.literal);inferred=NumericType()
                elif op in ('zeros','identidade'):
                    if types or not annotation.shape or (op=='identidade' and (len(annotation.shape)!=2 or annotation.shape[0]!=annotation.shape[1])):
                        raise TypeCheckError('Invalid SSA tensor constructor')
                    inferred=annotation
                elif op=='stack':
                    if not types or any(t!=types[0] for t in types):raise TypeCheckError('Irregular SSA stack')
                    inferred=NumericType((len(types),*types[0].shape))
                elif op=='copy':
                    if len(types)!=1:raise TypeCheckError('Copy arity mismatch')
                    inferred=types[0]
                else:
                    inferred=infer_operation(op,types)
                    if op=='^':
                        exponent=definitions[value.arguments[1]][2]
                        if exponent.operator!='num':raise TypeCheckError('SSA exponent must be literal')
                        n,d=_rational(exponent.literal)
                        if d!=1 or not 0<=n<=20:raise TypeCheckError('SSA exponent outside 0..20')
                if inferred!=annotation:raise TypeCheckError('Incorrect SSA result type')
        term=block.terminator
        for index,ref in enumerate(term.operands):
            inferred=use(ref,name,len(block.values),index)
            if term.kind=='branch' and not inferred.scalar:raise TypeCheckError('Branch condition must be scalar')
    values={ref:{'block':owner,'index':index,'operator':v.operator,'type':v.annotation.to_dict(),
                  'arguments':list(v.arguments),'incoming':[list(e) for e in v.incoming],'literal':v.literal,'uses':uses[ref]}
            for ref,(owner,index,v) in sorted(definitions.items())}
    return {'format':'omega-ssa-analysis-1','entry':graph.entry,
            'blocks':{name:{'successors':list(successors[name]),'predecessors':sorted(predecessors[name]),
                            'dominators':[d for d in names if dominates(d,name)],'immediate_dominator':immediate[name],
                            'dominance_frontier':sorted(frontiers[name]),
                            'terminator':{'kind':blocks[name].terminator.kind,'operands':list(blocks[name].terminator.operands)}}
                      for name in names},'values':values}


def tensor_graph(ir):
    if type(ir) is not TypedIR:raise TypeCheckError('Tensor SSA import requires validated TypedIR')
    legacy=ir.legacy();values=[]
    for i,node in enumerate(legacy['nos']):
        values.append(Value('n'+str(i),'input' if node['op']=='param' else node['op'],
                            tuple('n'+str(j) for j in node['args']),NumericType(tuple(node['forma'])),
                            literal=node.get('v')))
    # Name tables select results. Repeated aliases do not create new definitions.
    outputs=tuple('n'+str(i) for i in sorted(set(legacy['simbolos'].values())))
    return Graph('entry',(Block('entry',tuple(values),Terminator('return',(),outputs)),))


def analyze_tensor(ir):
    graph=tensor_graph(ir)
    result=analyze(graph)
    result['typed_ir_sha256']=ir.sha256
    result['scope']='single pure tensor graph evaluation; mutable commands are not lowered'
    return result


def verify_analysis(graph,report):
    if type(report) is not dict:raise TypeCheckError('Malformed SSA analysis')
    try:matches=_encode(report)==_encode(analyze(graph))
    except (ValueError,TypeError,RecursionError):raise TypeCheckError('Malformed SSA analysis') from None
    if not matches:raise TypeCheckError('SSA analysis does not match graph')
    return True
