"""Atomic data-only metadata and weights-only PyTorch checkpoints."""
import hashlib,json,os,tempfile
from pathlib import Path
class Checkpoints:
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    def save(self,name,model,metadata):
        import torch
        if not name.isidentifier():raise ValueError('Invalid checkpoint name')
        target=self.root/(name+'.pt')
        if target.exists():raise FileExistsError(target)
        fd,tmp=tempfile.mkstemp(dir=self.root);os.close(fd)
        try:
            torch.save(model.state_dict(),tmp);digest=hashlib.sha256(Path(tmp).read_bytes()).hexdigest();os.link(tmp,target)
        finally:Path(tmp).unlink(missing_ok=True)
        record={**metadata,'sha256':digest,'weights':target.name}
        with (self.root/(name+'.json')).open('x') as stream:json.dump(record,stream,sort_keys=True,allow_nan=False)
        return record
    def load(self,name,model):
        if not isinstance(name,str) or not name.isidentifier():raise ValueError('Invalid checkpoint name')
        import torch
        record=json.loads((self.root/(name+'.json')).read_text());path=self.root/record['weights']
        if path.parent.resolve()!=self.root.resolve() or path.is_symlink():raise ValueError('Invalid checkpoint path')
        if path.stat().st_size>1024**3 or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Checkpoint integrity mismatch')
        model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True));return record
