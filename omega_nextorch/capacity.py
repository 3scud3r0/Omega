"""Capacity edits produce copies. Gains and preservation must be measured externally."""
import copy
from nextorch.evolution.net2net import Net2NetExpansion
def expand(model,index,width,generator=None):return Net2NetExpansion.widen_sequential(model,index,width,generator)
def prune_weights(model,fraction):
    import torch
    if not 0<=fraction<1:raise ValueError('Invalid pruning fraction')
    candidate=copy.deepcopy(model);pruned=0;total=0
    with torch.no_grad():
        for parameter in candidate.parameters():
            if parameter.ndim<2:continue
            flat=parameter.abs().flatten();count=int(flat.numel()*fraction);total+=flat.numel()
            if count:
                indices=torch.argsort(flat,stable=True)[:count];parameter.view(-1)[indices]=0;pruned+=count
    return candidate,{'pruned':pruned,'eligible':total,'structural_speedup_claimed':False}
