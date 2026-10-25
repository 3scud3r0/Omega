"""Notebook code executes only in a process sandbox, without inherited credentials."""
import hashlib,json,sys,sysconfig,tempfile
from pathlib import Path
from omega_platform.sandbox import run
from omega_platform.budget import Budget
def execute(notebook,*,capability,verifier,principal,budget=Budget()):
    verifier.require(capability,principal,'code.execute')
    if type(notebook) is not dict or notebook.get('nbformat')!=4 or len(notebook.get('cells',()))>64:raise ValueError('Notebook format/budget invalid')
    code=[]
    for cell in notebook['cells']:
        if cell.get('cell_type')!='code':continue
        source=''.join(cell.get('source',())) if type(cell.get('source')) is list else cell.get('source','')
        if not isinstance(source,str) or any(line.lstrip().startswith(('%','!')) for line in source.splitlines()):raise ValueError('Notebook magics/shell cells unsupported')
        code.append(source)
    source='\n\n'.join(code)
    if len(source.encode())>1024*1024:raise ValueError('Notebook code budget exceeded')
    site=Path(sysconfig.get_paths()['purelib'])
    with tempfile.TemporaryDirectory(prefix='omega-notebook-') as tmp:
        path=Path(tmp)/'cells.py';path.write_text('import sys\nsys.path.insert(0,'+repr(str(site))+')\n'+source)
        result=run([sys.executable,path],readonly=[path,site,Path(sys.base_prefix)],budget=budget)
    return {'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'cells':len(code),'returncode':result.returncode,
            'stdout':result.stdout,'stderr':result.stderr,'sandboxed':result.sandboxed,'termination':result.termination}
