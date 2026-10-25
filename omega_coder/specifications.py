from dataclasses import dataclass
@dataclass(frozen=True)
class Acceptance:
    id: str
    description: str
    oracle: str
    fixtures: tuple[str,...]=()
    def __post_init__(self):
        if not self.id or not self.description or not self.oracle:raise ValueError('Executable acceptance contract required')
@dataclass(frozen=True)
class Specification:
    requirement: str
    acceptance: tuple[Acceptance,...]
    preserved_interfaces: tuple[str,...]=()
    def __post_init__(self):
        if not self.requirement or not self.acceptance or len({a.id for a in self.acceptance})!=len(self.acceptance):raise ValueError('Invalid specification')
def from_requirements(requirement,contracts):
    return Specification(requirement,tuple(Acceptance(**item) for item in contracts))
