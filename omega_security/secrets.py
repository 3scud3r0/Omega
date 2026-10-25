"""Redaction reduces disclosure; it is not a substitute for capability isolation."""
import re
PATTERNS=(re.compile(r'(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+'),
          re.compile(r'(?i)((?:api[_-]?key|password|token|secret)\s*[=:]\s*)[^\s,;]+'))
def redact(value,known=()):
    if isinstance(value,dict):
        return {k:('[REDACTED]' if re.search(r'(?i)(secret|password|token|authorization|api.?key)',str(k)) else redact(v,known)) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [redact(v,known) for v in value]
    if not isinstance(value,str):return value
    for secret in sorted((s for s in known if s),key=len,reverse=True):value=value.replace(secret,'[REDACTED]')
    for pattern in PATTERNS:value=pattern.sub(lambda m:m.group(1)+'[REDACTED]',value)
    return value
