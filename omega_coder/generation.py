"""Generators return source data; executing it requires an isolated runner."""
from dataclasses import dataclass
import hashlib
LANGUAGES=frozenset({'omega','python','c','lean'})
@dataclass(frozen=True)
class Candidate:
    language: str
    source: str
    origin: str
    def __post_init__(self):
        if self.language not in LANGUAGES or len(self.source.encode())>1024*1024:raise ValueError('Invalid candidate')
    @property
    def sha256(self):return hashlib.sha256(self.source.encode()).hexdigest()
def generate(specification,provider,language,limit=16):
    if language not in LANGUAGES or not 1<=limit<=256:raise ValueError('Invalid generation request')
    result=[];seen=set()
    for text in provider(specification,language,limit):
        if len(result)>=limit:break
        candidate=Candidate(language,text,type(provider).__name__)
        if candidate.sha256 not in seen:result.append(candidate);seen.add(candidate.sha256)
    return tuple(result)
