from dataclasses import dataclass
from pathlib import PurePosixPath
@dataclass(frozen=True)
class Component:
    id: str
    paths: tuple[str,...]
    mutable: bool
    required_checks: tuple[str,...]
class ComponentRegistry:
    def __init__(self,components):
        components=tuple(components);self.components={c.id:c for c in components}
        if len(components)!=len(self.components):raise ValueError('Duplicate component')
    def require_patch(self,component,paths):
        item=self.components[component]
        if not item.mutable:raise PermissionError('Protected component')
        for path in paths:
            p=PurePosixPath(path)
            if p.is_absolute() or '..' in p.parts or not any(path==allowed or path.startswith(allowed.rstrip('/')+'/') for allowed in item.paths):raise PermissionError('Patch exceeds authorized component')
        return item.required_checks
