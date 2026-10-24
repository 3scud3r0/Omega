"""Validated OS resource budgets; absence of a limit is not an allowed default."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Budget:
    wall_seconds: float = 30.0
    cpu_seconds: int = 15
    memory_bytes: int = 512 * 1024 * 1024
    output_bytes: int = 8 * 1024 * 1024
    file_bytes: int = 64 * 1024 * 1024
    processes: int = 128
    open_files: int = 128
    stack_bytes: int = 16 * 1024 * 1024
    fuel: int = 5_000_000
    depth: int = 256

    def __post_init__(self):
        if isinstance(self.wall_seconds, bool) or not isinstance(self.wall_seconds,(int,float)) or not isfinite(self.wall_seconds) or not 0 < self.wall_seconds <= 3600:
            raise ValueError('wall_seconds must be finite and in (0,3600]')
        bounds={'cpu_seconds':(1,3600),'memory_bytes':(32*1024*1024,64*1024**3),
                'output_bytes':(1024,64*1024*1024),'file_bytes':(1024,1024**3),
                'processes':(1,1024),'open_files':(16,4096),'stack_bytes':(1024**2,64*1024**2),
                'fuel':(1,500_000_000),'depth':(1,512)}
        for name,(lower,upper) in bounds.items():
            v=getattr(self,name)
            if type(v) is not int or not lower <= v <= upper:
                raise ValueError(f'{name} must be an integer in [{lower},{upper}]')


COMPILER_BUDGET=Budget(wall_seconds=180,cpu_seconds=120,memory_bytes=2*1024**3,
                       fuel=500_000_000,depth=512)
BUILD_BUDGET=Budget(wall_seconds=300,cpu_seconds=240,memory_bytes=4*1024**3,
                    file_bytes=512*1024**2,processes=1024,fuel=500_000_000,depth=512)
PROOF_BUDGET=Budget(wall_seconds=300,cpu_seconds=240,memory_bytes=4*1024**3,
                    file_bytes=512*1024**2,processes=1024,fuel=500_000_000,depth=512)
