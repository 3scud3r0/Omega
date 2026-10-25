"""Review findings are advisory; they do not establish correctness."""
from pathlib import PurePosixPath
from omega_security.secrets import redact
PROTECTED=('.github/','formal/','omega_security/','omega_evolution/promotion.py')
def review(changes,protected=PROTECTED):
    findings=[]
    for path,content in sorted(changes.items()):
        p=PurePosixPath(path)
        if p.is_absolute() or '..' in p.parts:findings.append({'path':path,'severity':'block','reason':'path escape'})
        if any(path.startswith(prefix) for prefix in protected):findings.append({'path':path,'severity':'review','reason':'trusted component change'})
        if redact(content)!=content:findings.append({'path':path,'severity':'block','reason':'possible secret disclosure'})
        if path.endswith('.lean') and any(word in content.split() for word in ('sorry','admit','axiom')):findings.append({'path':path,'severity':'block','reason':'proof admission declaration'})
    return {'findings':findings,'blocked':any(f['severity']=='block' for f in findings),'requires_independent_review':True}
