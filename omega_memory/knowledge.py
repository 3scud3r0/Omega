from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class Claim:
    subject: str
    predicate: str
    object: str
    evidence: tuple[str,...]
    def __post_init__(self):
        if not self.subject or not self.predicate or not self.evidence:raise ValueError('Claim provenance required')
    @property
    def id(self):return hashlib.sha256(json.dumps([self.subject,self.predicate,self.object],ensure_ascii=False).encode()).hexdigest()
class KnowledgeBase:
    def __init__(self):self.claims={}
    def add(self,claim):
        previous=self.claims.get(claim.id)
        if previous:claim=Claim(claim.subject,claim.predicate,claim.object,tuple(sorted(set(previous.evidence)|set(claim.evidence))))
        self.claims[claim.id]=claim;return claim.id
    def conflicts(self):
        groups={}
        for claim in self.claims.values():groups.setdefault((claim.subject,claim.predicate),[]).append(claim)
        return {k:tuple(v) for k,v in groups.items() if len({c.object for c in v})>1}
    def query(self,subject,predicate):return tuple(c for c in self.claims.values() if c.subject==subject and c.predicate==predicate)
