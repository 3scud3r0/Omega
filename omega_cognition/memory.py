"""Last-use interval allocation for flat static tensor graphs."""
from omega.certified_graph import validate
from omega.certified_proof import check


def dependencies(node):
    if node['op']=='affine':return [ref for ref,_ in node['terms']]
    if node['op'] in ('mul','div'):return [node['left'],node['right']]
    return [node['input']]


def plan_buffers(graph,*,bytes_per_value=16,prove=True):
    validate(graph)
    if type(bytes_per_value) is not int or not 1<=bytes_per_value<=4096:raise ValueError('Fixed value width required')
    count=graph['inputs']+len(graph['nodes']);last=list(range(count));starts=[0]*graph['inputs']+list(range(graph['inputs'],count))
    for i,node in enumerate(graph['nodes'],graph['inputs']):
        for ref in dependencies(node):last[ref]=max(last[ref],i)
    for ref in graph['outputs']:last[ref]=count
    slots=[];ends=[]
    for i,start in enumerate(starts):
        free=next((slot for slot,end in enumerate(ends) if end<start),None)
        if free is None:free=len(ends);ends.append(last[i])
        else:ends[free]=last[i]
        slots.append(free)
    obligations=[];previous={}
    for i,slot in enumerate(slots):
        if slot in previous:
            j=previous[slot]
            if not last[j]<starts[i]:raise ValueError('Buffer liveness overlap')
            obligations.append((j,i))
        previous[slot]=i
    result={'slots':slots,'starts':starts,'last_uses':last,'slot_count':len(ends),'bytes':len(ends)*bytes_per_value,
            'unreused_bytes':count*bytes_per_value,'allocation':'fixed buffers; no hidden dynamic tensor allocation'}
    if prove:
        lines=['import Omega.LinearMemory','namespace OmegaBufferPlan','set_option maxRecDepth 10000'];names=[]
        # One proof per reused slot covers every pair sharing that slot.
        for slot in range(len(ends)):
            pairs=[(i,j) for i,j in obligations if slots[i]==slot]
            claims=[f'({last[i]} < {starts[j]} ∨ {last[j]} < {starts[i]})' for i,j in pairs]
            lines += [f'theorem slot_{slot} : '+(' ∧ '.join(claims) if claims else 'True')+' := by norm_num',f'#print axioms slot_{slot}']
            names.append(f'OmegaBufferPlan.slot_{slot}')
        lines.append('end OmegaBufferPlan');source='\n'.join(lines)+'\n'
        result['proof']=source;result['admission']=check(source,names)
    return result
