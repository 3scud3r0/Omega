"""Native build policy; no process-global compiler-option mutation."""
from pathlib import Path
from . import driver
LEVELS=frozenset({'-O0','-O1','-O2','-O3','-Os'})
def build(source,destination,*,level='-O2',rewrite=False):
    if level not in LEVELS:raise ValueError('Unsupported optimization level')
    return driver.build(source,destination,optimize=rewrite,optimization=level)
def compare(source,directory,*,levels=('-O0','-O2','-O3')):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    results=[]
    for level in levels:
        binary=directory/('program'+level.replace('-','_'))
        build(source,binary,level=level)
        data,admission=driver.run(binary)
        signature={k:data[k] for k in ('state','values','outputs')}
        if results and signature!=results[0]['signature']:raise ValueError('Backend semantic disagreement')
        results.append({'level':level,'signature':signature,'admission':admission})
    return results
