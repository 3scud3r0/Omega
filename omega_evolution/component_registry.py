"""A supervisor-owned, immutable inventory of permitted source boundaries."""
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType


def _path(value):
    if type(value) is not str or not 0 < len(value) <= 4096 or '\\' in value or ':' in value or '\0' in value:
        raise PermissionError('Invalid component path')
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or not path.parts or any(p in {'.', '..', '.git'} for p in path.parts):
        raise PermissionError('Unsafe component path')
    return value


@dataclass(frozen=True)
class Component:
    id: str
    paths: tuple[str, ...]
    mutable: bool
    required_checks: tuple[str, ...]

    def __post_init__(self):
        if type(self.id) is not str or not 0 < len(self.id) <= 256 or type(self.mutable) is not bool:
            raise ValueError('Invalid component identity/policy')
        if type(self.paths) is not tuple or not 1 <= len(self.paths) <= 256:
            raise ValueError('Explicit component paths required')
        for path in self.paths:
            _path(path)
        if type(self.required_checks) is not tuple or not 1 <= len(self.required_checks) <= 128:
            raise ValueError('Required invariant names must be explicit')
        if any(type(name) is not str or not 0 < len(name) <= 256 for name in self.required_checks):
            raise ValueError('Invalid invariant name')
        if len(set(self.paths)) != len(self.paths) or len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError('Duplicate component paths/checks')


class ComponentRegistry:
    def __init__(self, components):
        items = []
        for component in components:
            if len(items) >= 1024 or type(component) is not Component:
                raise ValueError('Bounded typed component inventory required')
            items.append(component)
        mapped = {c.id: c for c in items}
        if len(mapped) != len(items):
            raise ValueError('Duplicate component')
        # A protected subtree must not become writable through a broader component.
        for mutable in items:
            if not mutable.mutable:
                continue
            for protected in items:
                if protected.mutable:
                    continue
                for allowed in mutable.paths:
                    for denied in protected.paths:
                        if allowed == denied or allowed.startswith(denied + '/') or denied.startswith(allowed + '/'):
                            raise ValueError('Mutable component overlaps a protected component')
        self.components = MappingProxyType(mapped)

    def require_patch(self, component, paths):
        item = self.components[component]
        if not item.mutable:
            raise PermissionError('Protected component')
        count = 0
        for path in paths:
            count += 1
            if count > 1024:
                raise ValueError('Patch path budget exceeded')
            _path(path)
            if not any(path == allowed or path.startswith(allowed + '/') for allowed in item.paths):
                raise PermissionError('Patch exceeds authorized component')
        if count == 0:
            raise ValueError('Empty patch scope')
        return item.required_checks
