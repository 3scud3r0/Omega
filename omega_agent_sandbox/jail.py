"""Host-owned containment shared by every cognitive mode. No unsafe fallback."""
from dataclasses import dataclass,asdict
from pathlib import Path
from omega_platform.budget import Budget
from omega_platform.sandbox import run


@dataclass(frozen=True)
class Jail:
    wall_seconds:int=60
    cpu_seconds:int=45
    memory_bytes:int=1024**3
    stack_bytes:int=8*1024**2
    fuel:int=50_000_000
    depth:int=256

    def __post_init__(self):
        limits={'wall_seconds':(1,300),'cpu_seconds':(1,240),'memory_bytes':(32*1024**2,8*1024**3),
                'stack_bytes':(1024**2,64*1024**2),'fuel':(1,500_000_000),'depth':(1,512)}
        for k,(lo,hi) in limits.items():
            if type(getattr(self,k)) is not int or not lo<=getattr(self,k)<=hi:raise ValueError('Cognitive jail quota: '+k)
    def budget(self):return Budget(**asdict(self),output_bytes=1024**2,file_bytes=16*1024**2,processes=128)
    def execute(self,argv,*,readonly=(),writable=(),cwd=None,threads=False):
        arguments={'readonly':readonly,'writable':writable,'budget':self.budget(),'threads':threads}
        if cwd is not None:arguments['cwd']=cwd
        return run(argv,**arguments)
