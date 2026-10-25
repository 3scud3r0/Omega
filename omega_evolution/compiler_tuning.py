from pathlib import Path
from omega_selfhost.native_backend import build
from omega_selfhost.driver import run
def evaluate(source,root,measure,levels=('-O0','-O2','-O3')):
    root=Path(root);root.mkdir(parents=True,exist_ok=False);results=[];reference=None
    for i,level in enumerate(levels):
        binary=root/('candidate_'+str(i));build(source,binary,level=level)
        data,proof=run(binary);semantic={k:data[k] for k in ('outputs','state','values')}
        if reference is not None and semantic!=reference:raise ValueError('Compiler tuning changed semantics')
        reference=semantic;results.append({'level':level,'cost':measure(binary),'admission':proof})
    return {'candidates':results,'selected_for_review':min(results,key=lambda r:r['cost']),'promoted':False}
