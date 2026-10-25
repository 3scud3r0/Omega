from pathlib import Path
from .worker import invoke
from omega_platform.budget import Budget
def query(path,sql,parameters=(),*,write=False,capability,verifier,principal,approval=None,approval_gate=None,budget=Budget()):
    if type(write) is not bool:raise TypeError('Explicit boolean write mode required')
    path=Path(path).resolve(strict=True);verifier.require(capability,principal,'database.write' if write else 'database.read',path=path)
    if not isinstance(sql,str) or len(sql)>65536:raise ValueError('Query budget exceeded')
    keyword=sql.lstrip().split(None,1)[0].upper()
    if keyword not in ({'SELECT','INSERT','UPDATE','DELETE'} if write else {'SELECT'}):raise PermissionError('SQL operation not authorized')
    action={'path':str(path),'sql':sql,'parameters':parameters}
    if write:
        if approval_gate is None:raise PermissionError('Mutation approval gate required')
        approval_gate.consume(action,approval,principal)
    request={**action,'query':sql,'write':write}
    return invoke('database_worker',request,readonly=[] if write else [path],writable=[path.parent] if write else [],budget=budget)
