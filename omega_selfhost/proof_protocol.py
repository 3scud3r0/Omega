"""Canonical data-only proof envelopes; no supplied Lean source is evaluated."""
import hashlib,json
from omega.typed_ir import _pairs
FORMAT='omega-proof-envelope-1'
def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def statement_hash(statement):return hashlib.sha256(encode(statement)).hexdigest()
def envelope(statement,certificate,checker,dependencies):
    if type(checker) is not str or not checker:raise ValueError('Checker identity required')
    return {'format':FORMAT,'statement':statement,'statement_sha256':statement_hash(statement),
            'certificate':certificate,'checker':checker,'dependencies':sorted(set(dependencies))}
def decode(data):
    if type(data) is not bytes or len(data)>8*1024**2:raise ValueError('Proof byte budget exceeded')
    obj=json.loads(data,object_pairs_hook=_pairs)
    fields={'format','statement','statement_sha256','certificate','checker','dependencies'}
    if type(obj) is not dict or set(obj)!=fields or obj['format']!=FORMAT:raise ValueError('Unknown proof envelope')
    if obj['statement_sha256']!=statement_hash(obj['statement']) or encode(obj)!=data:raise ValueError('Ambiguous or changed proof')
    if type(obj['dependencies']) is not list or obj['dependencies']!=sorted(set(obj['dependencies'])):raise ValueError('Invalid dependencies')
    return obj
