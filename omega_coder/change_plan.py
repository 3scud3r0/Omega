from dataclasses import dataclass
from pathlib import PurePosixPath
@dataclass(frozen=True)
class Change:
    path: str
    reason: str
    depends_on: tuple[str,...]=()
    def __post_init__(self):
        path=PurePosixPath(self.path)
        if path.is_absolute() or '..' in path.parts or not self.reason:raise ValueError('Unsafe/unjustified change')
def plan(changes,index):
    changes=tuple(changes);names={c.path for c in changes}
    if len(names)!=len(changes):raise ValueError('Duplicate changed path')
    done=set();ordered=[]
    while len(done)<len(names):
        ready=sorted((c for c in changes if c.path not in done and set(c.depends_on)<=done),key=lambda c:c.path)
        if not ready:raise ValueError('Cyclic/missing change dependency')
        for change in ready:done.add(change.path);ordered.append(change)
    impacts={c.path:tuple(sorted(p for p,r in index.items() if c.path.replace('/','.') in str(r.get('imports',())))) for c in changes}
    return {'changes':tuple(ordered),'potential_dependents':impacts}
