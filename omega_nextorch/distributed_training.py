"""DDP requires an explicitly initialized host process group; no implicit network setup."""
from omega_learning.versioning import Checkpoints
def wrap(model,device_ids=None):
    import torch
    if not torch.distributed.is_available() or not torch.distributed.is_initialized():raise RuntimeError('Host must initialize the distributed process group')
    return torch.nn.parallel.DistributedDataParallel(model,device_ids=device_ids)
def partition(ids,rank,world_size):
    if not 0<=rank<world_size or world_size<1:raise ValueError('Invalid distributed rank')
    return tuple(sorted(set(ids)))[rank::world_size]
def checkpoint(model,root,name,metadata):
    import torch
    group=torch.distributed
    if not group.is_initialized():raise RuntimeError('Distributed group unavailable')
    result=None
    if group.get_rank()==0:result=Checkpoints(root).save(name,model.module if hasattr(model,'module') else model,metadata)
    group.barrier();return result
