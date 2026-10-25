"""Origin labeling and data-only extraction; arbitrary documents grant no authority."""
from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class UntrustedDocument:
    source: str
    content: bytes
    observed_at: str
    def __post_init__(self):
        if not self.source or type(self.content) is not bytes or len(self.content)>8*1024**2:raise ValueError('Invalid untrusted document')
    @property
    def digest(self):return hashlib.sha256(self.content).hexdigest()
def data_envelope(document):
    if type(document) is not UntrustedDocument:raise TypeError('Origin-labeled document required')
    return {'kind':'untrusted_data','source':document.source,'sha256':document.digest,
            'observed_at':document.observed_at,'content':document.content.decode('utf-8','replace'),'authority':False}
def extract_json(document,allowed_fields):
    value=json.loads(document.content)
    if type(value) is not dict or not set(value)<=set(allowed_fields):raise ValueError('Unexpected document fields')
    return value
