"""Explicit architecture + weights-only checkpoints to freestanding exact C."""
from pathlib import Path
import json


def export(checkpoint,architecture,directory,*,input_bounds,output_bounds,input_scale=1):
    import torch
    from omega.certify import trace
    from omega.edge import emit
    if type(architecture) is not list or not 1<=len(architecture)<=32:raise ValueError('A bounded explicit architecture is required')
    layers=[]
    for layer in architecture:
        if layer=={'type':'relu'}:layers.append(torch.nn.ReLU())
        elif type(layer) is dict and set(layer)=={'type','in','out','bias'} and layer['type']=='linear':
            if any(type(layer[k]) is not int or not 1<=layer[k]<=256 for k in ('in','out')) or type(layer['bias']) is not bool:raise ValueError('Static linear dimensions required')
            layers.append(torch.nn.Linear(layer['in'],layer['out'],bias=layer['bias']))
        else:raise ValueError('Standalone lowering accepts explicit affine/ReLU layers')
    if not isinstance(layers[0],torch.nn.Linear):raise ValueError('Architecture starts with a known input width')
    path=Path(checkpoint)
    if path.is_symlink() or path.stat().st_size>64*1024**2:raise ValueError('Bounded regular weights-only checkpoint required')
    model=torch.nn.Sequential(*layers);weights=torch.load(path,map_location='cpu',weights_only=True)
    model.load_state_dict(weights,strict=True);model.eval()
    graph=trace(model,torch.zeros(layers[0].in_features))
    result=emit(graph,input_bounds,output_bounds,directory,input_scale=input_scale)
    from .memory import plan_buffers
    result['memory_plan']=plan_buffers(graph,bytes_per_value=8)
    # Materialize the proven allocation instead of merely reporting it.
    import re
    source=Path(result['source']);text=source.read_text();slots=result['memory_plan']['slots']
    text=re.sub(r'\b(?:const\s+)?int64_t\s+x(\d+)\s*=',lambda m:f'buffer[{slots[int(m.group(1))]}] =',text)
    text=re.sub(r'\bx(\d+)\b',lambda m:f'buffer[{slots[int(m.group(1))]}]',text)
    marker='int omega_edge(const int64_t *input, int64_t *output) {'
    if text.count(marker)!=1:raise ValueError('Unknown freestanding emitter layout')
    text=text.replace(marker,marker+f'\n  int64_t buffer[{result["memory_plan"]["slot_count"]}];',1)
    source.write_text(text)
    root=Path(directory);(root/'memory-plan.json').write_text(json.dumps(result['memory_plan'],sort_keys=True,indent=2)+'\n')
    return result
