"""Private parsing workers get only bounded requests and explicit mounts."""
import json,sys,sysconfig,tempfile
from pathlib import Path
from omega_platform.sandbox import run
from omega_platform.budget import Budget
WORKERS=frozenset({'document_worker','database_worker'})
def invoke(name,request,*,readonly=(),writable=(),budget=Budget()):
    if name not in WORKERS:raise ValueError('Unknown trusted worker')
    data=json.dumps(request,allow_nan=False).encode()
    if len(data)>16*1024**2:raise ValueError('Worker input budget exceeded')
    site=Path(sysconfig.get_paths()['purelib']);worker=Path(__file__).with_name(name+'.py')
    with tempfile.TemporaryDirectory(prefix='omega-tool-') as tmp:
        path=Path(tmp)/'request.json';path.write_bytes(data)
        result=run([sys.executable,worker,site,path],readonly=[worker,site,Path(sys.base_prefix),path,*readonly],writable=writable,budget=budget,check=True)
    return json.loads(result.stdout)
