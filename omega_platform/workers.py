"""Authenticated worker RPC adapter; transport/network authority belongs to the host."""
from dataclasses import dataclass,asdict
import hashlib,json,base64
from .scheduler import Job,execute,BatchLimits
@dataclass(frozen=True)
class Worker:
    id: str
    endpoint: str
    slots: int
    def __post_init__(self):
        if not self.id or not self.endpoint.startswith('https://') or not 1<=self.slots<=8:raise ValueError('Invalid worker')
class Coordinator:
    def __init__(self,workers,transport,authenticate,verifier,principal):
        self.workers=tuple(sorted(workers,key=lambda w:w.id));self.transport=transport;self.authenticate=authenticate;self.verifier=verifier;self.principal=principal
        if not self.workers or len({w.id for w in self.workers})!=len(self.workers):raise ValueError('Unique authenticated workers required')
    def dispatch(self,jobs,capabilities):
        results=[]
        for index,job in enumerate(jobs):
            if index>=64:raise ValueError('Distributed queue budget exceeded')
            worker=self.workers[index%len(self.workers)];self.verifier.require(capabilities[worker.id],self.principal,'worker.execute:'+worker.id)
            payload=asdict(job);digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            response=self.transport(worker.endpoint,{'job':payload,'sha256':digest})
            if response.get('job_sha256')!=digest or self.authenticate(worker,response) is not True:raise PermissionError('Worker response authentication failed')
            results.append((job.id,response))
        return tuple(results)
def local(jobs,limits=BatchLimits()):return execute(jobs,limits)

class WorkerServer:
    """Transport-neutral server handler; a host supplies authentication/signing.

    Only explicitly whitelisted system executables bypass artifact-root scope.
    The request grants no writable mounts and cannot inherit host credentials.
    """
    def __init__(self,id,verifier,principal,sign,system_executables=(),limits=BatchLimits()):
        from pathlib import Path
        self.id=id;self.verifier=verifier;self.principal=principal;self.sign=sign
        self.executables=frozenset(str(Path(p).resolve(strict=True)) for p in system_executables);self.limits=limits
    def handle(self,request,capability):
        from pathlib import Path
        from .budget import Budget
        self.verifier.require(capability,self.principal,'worker.execute:'+self.id)
        payload=request['job'];digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if request.get('sha256')!=digest:raise ValueError('Worker request digest mismatch')
        if set(payload)!={'id','argv','readonly','budget'}:raise ValueError('Unknown worker job fields')
        job=Job(payload['id'],tuple(payload['argv']),tuple(payload['readonly']),Budget(**payload['budget']))
        executable=str(Path(job.argv[0]).resolve(strict=True))
        if executable not in self.executables:self.verifier.require(capability,self.principal,'code.execute',path=executable)
        for path in job.readonly:self.verifier.require(capability,self.principal,'artifact.read',path=path)
        id,outcome=execute((job,),self.limits)[0]
        result={'worker':self.id,'job_id':id,'job_sha256':digest,'returncode':outcome.returncode,
                'stdout':outcome.stdout,'stderr':outcome.stderr,'termination':outcome.termination,'sandboxed':outcome.sandboxed}
        canonical=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
        result['signature']=base64.b64encode(self.sign(canonical)).decode('ascii')
        return result


def verify_response(worker,response,verify_signature):
    value=dict(response)
    try:signature=base64.b64decode(value.pop('signature'),validate=True)
    except (ValueError,KeyError,TypeError):return False
    payload=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    return value.get('worker')==worker.id and verify_signature(worker.id,payload,signature) is True
