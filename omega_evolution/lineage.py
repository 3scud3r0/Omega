from dataclasses import dataclass
@dataclass(frozen=True)
class Version:
    id: str
    parents: tuple[str,...]
    experiment: str
    artifact_digest: str
class Lineage:
    def __init__(self):self.versions={}
    def add(self,version):
        if not version.id or version.id in self.versions or any(p not in self.versions for p in version.parents):raise ValueError('Invalid version ancestry')
        if not version.experiment or len(version.artifact_digest)!=64:raise ValueError('Provenance required')
        self.versions[version.id]=version
    def ancestors(self,id):
        visited=set();pending=[id]
        while pending:
            node=pending.pop()
            if node in visited:continue
            visited.add(node);pending.extend(self.versions[node].parents)
        return tuple(sorted(visited))
