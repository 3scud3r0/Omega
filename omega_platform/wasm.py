"""WASM worker has no WASI/imports and also runs under the OS sandbox."""
import json,sys,sysconfig,tempfile
from pathlib import Path
from .budget import Budget
from .sandbox import run
def execute(wat,arguments=(),*,budget=Budget(),fuel=1000000):
    if type(wat) is not str or len(wat.encode())>1024*1024:raise ValueError('WASM source budget exceeded')
    if type(fuel) is not int or not 1<=fuel<=500000000:raise ValueError('Invalid WASM fuel')
    if len(arguments)>64 or any(type(v) is not int or not -(2**63)<=v<2**63 for v in arguments):raise ValueError('i64 arguments required')
    worker=Path(__file__).with_name('wasm_worker.py');site=Path(sysconfig.get_paths()['purelib']).resolve()
    with tempfile.TemporaryDirectory(prefix='omega-wasm-') as tmp:
        request=Path(tmp)/'request.json';request.write_text(json.dumps({'wat':wat,'arguments':arguments,'fuel':fuel,'memory':min(budget.memory_bytes,64*1024**2)}))
        outcome=run([sys.executable,worker,str(site),request],readonly=[worker,site,request,Path(sys.base_prefix)],
                    threads=True,budget=budget,check=True)
        result=json.loads(outcome.stdout)
        if set(result)!={'value','fuel_remaining'}:raise ValueError('Invalid WASM worker result')
        return result
