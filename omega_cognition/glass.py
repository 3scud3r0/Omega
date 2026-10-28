"""Grounded logical coordinates and replayable arithmetic traces.

Orthogonality is a geometric property. Concept meaning requires an explicit
logical contract; an axis label alone never grants a semantic certificate.
"""
from fractions import Fraction as Q
import hashlib
from omega.certified_graph import validate,evaluate
from omega.certified_proof import check,rational_literal as lit
from omega_refine_check.contracts import verify_contract
from omega_selfhost.proof_protocol import encode


def orthogonal_basis(rows):
    if type(rows) not in (list,tuple) or not 1<=len(rows)<=64:raise ValueError('Bounded rational basis required')
    basis=[list(map(Q,row)) for row in rows];width=len(basis[0])
    if not 1<=width<=64 or len(basis)>width or any(len(row)!=width for row in basis):raise ValueError('Basis shape mismatch')
    lines=['import Omega.Glass','namespace OmegaBasis'];names=[]
    for i,row in enumerate(basis):
        for j,other in enumerate(basis):
            value=sum((a*b for a,b in zip(row,other)),Q(0));expected=Q(int(i==j))
            if value!=expected:raise ValueError('Concept axes must be exactly orthonormal')
            lines += [f'theorem dot_{i}_{j} : {lit(value)} = {lit(expected)} := by norm_num',f'#print axioms dot_{i}_{j}']
            names.append(f'OmegaBasis.dot_{i}_{j}')
    lines.append('end OmegaBasis');source='\n'.join(lines)+'\n'
    return {'basis':[[str(x) for x in row] for row in basis],'proof':source,'admission':check(source,names)}


def graph_ast(graph,ref):
    if ref<graph['inputs']:return ('var',f'input_{ref}')
    node=graph['nodes'][ref-graph['inputs']];op=node['op']
    if op=='affine':
        result=('const',node['bias'])
        for parent,weight in node['terms']:result=('+',result,('*',('const',weight),graph_ast(graph,parent)))
        return result
    if op=='relu':return ('relu',graph_ast(graph,node['input']))
    if op=='square':return ('*',graph_ast(graph,node['input']),graph_ast(graph,node['input']))
    if op in ('mul','div'):return ('*' if op=='mul' else '/',graph_ast(graph,node['left']),graph_ast(graph,node['right']))
    raise ValueError('Universal concept grounding currently requires rational arithmetic; real activations retain observational traces')


def certify_concepts(graph,basis,concepts,input_contracts):
    validate(graph);geometry=orthogonal_basis(basis)
    if len(basis[0])!=len(graph['outputs']) or len(concepts)!=len(basis):raise ValueError('Concept/basis/output shape mismatch')
    grounded=[]
    for row,concept in zip(basis,concepts):
        if type(concept) is not dict or set(concept)!={'name','ensures'}:raise ValueError('Every concept needs an explicit semantic contract')
        projection=('const','0')
        for weight,ref in zip(row,graph['outputs']):projection=('+',projection,('*',('const',str(Q(weight))),graph_ast(graph,ref)))
        proof=verify_contract(input_contracts,projection,concept['ensures'])
        grounded.append({'name':concept['name'],'proof':proof})
    return {'geometry':geometry,'concepts':grounded,'graph_sha256':hashlib.sha256(encode(graph)).hexdigest(),
            'scope':'declared logical predicates, not automatic natural-language neuron meaning'}


def trace(graph,inputs,*,annotations=None,thresholds=None):
    validate(graph)
    from omega.real_graph import execute,analyze
    values=execute(graph,inputs)
    from omega.certified_graph import real_operations
    boxes=analyze(graph,[(Q(x),Q(x)) for x in inputs])[0] if real_operations(graph) else [(x,x) for x in values]
    events=[];annotations=dict(annotations or {});thresholds=dict(thresholds or {})
    for i,node in enumerate(graph['nodes'],graph['inputs']):
        from .memory import dependencies
        event={'node':i,'operation':node['op'],'parents':dependencies(node),'value':str(values[i]),
               'real_interval':list(map(str,boxes[i])),'annotation':annotations.get(i)}
        if node['op']=='relu':event['branch']='positive' if values[node['input']]>0 else 'zero'
        if i in thresholds:
            limit=Q(thresholds[i]);a,b=boxes[i]
            event['threshold']={'value':str(limit),'decision':'above' if a>limit else 'below_or_equal' if b<=limit else 'uncertified'}
        events.append(event)
    body={'format':'omega-glass-trace-1','graph':graph,'inputs':list(map(lambda x:str(Q(x)),inputs)),
          'events':events,'outputs':[str(values[i]) for i in graph['outputs']]}
    return {**body,'sha256':hashlib.sha256(encode(body)).hexdigest()}


def replay(record):
    if 'certificate' in record:
        expected=certify_trace(record['graph'],record['inputs'],annotations={e['node']:e['annotation'] for e in record['events'] if e['annotation'] is not None},
                               thresholds={e['node']:e['threshold']['value'] for e in record['events'] if 'threshold' in e})
        if encode(expected)!=encode(record):raise ValueError('Changed certified glass trace')
        return {'valid':True,'outputs':expected['outputs']}
    expected=trace(record['graph'],record['inputs'],annotations={e['node']:e['annotation'] for e in record['events'] if e['annotation'] is not None},
                   thresholds={e['node']:e['threshold']['value'] for e in record['events'] if 'threshold' in e})
    if encode(expected)!=encode(record):raise ValueError('Changed or unrelated glass trace')
    return {'valid':True,'outputs':expected['outputs']}


def certify_trace(graph,inputs,*,annotations=None,thresholds=None):
    record=trace(graph,inputs,annotations=annotations,thresholds=thresholds)
    from omega.certified_graph import certify_bounds
    selected=sorted(thresholds or graph['outputs'])
    proof_graph={**graph,'outputs':selected}
    proof_graph.pop('output_shape',None)
    events={e['node']:e for e in record['events']}
    output_bounds=[events[i]['real_interval'] if i>=graph['inputs'] else [str(Q(inputs[i]))]*2 for i in selected]
    source,admission=certify_bounds(proof_graph,[(Q(x),Q(x)) for x in inputs],output_bounds)
    body={k:v for k,v in record.items() if k!='sha256'}
    body['certificate']={'proof':source,'admission':admission,'selected':selected}
    return {**body,'sha256':hashlib.sha256(encode(body)).hexdigest()}


def native_trace(graph,inputs,directory,input_bounds,**options):
    from omega.real_native import build_runtime,run_runtime
    build_runtime(graph,directory,input_bounds,trace_values=True)
    outputs,admission=run_runtime(graph,__import__('pathlib').Path(directory)/'model',inputs)
    record=certify_trace(graph,inputs,**options)
    if outputs!=record['outputs'] or admission.get('native_trace')!=[str(v) for v in __import__('omega.real_graph',fromlist=['execute']).execute(graph,inputs)]:
        raise ValueError('Native intermediate trace differs from certified replay')
    return {'trace':record,'native_admission':admission}
