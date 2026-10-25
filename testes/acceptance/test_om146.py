"""OM-146: executable checks; source delivery, not a recorded pass."""
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from omega_platform.workers import Worker,WorkerServer,Coordinator,verify_response
from omega_platform.scheduler import Job
from omega_platform.budget import Budget
from omega_security.signatures import SignatureVerifier

def test_authenticated_worker_rpc_matches_jobs_rejects_replay_and_tampering(signed_authority):
    verifier,mint=signed_authority;private=Ed25519PrivateKey.generate()
    public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    signatures=SignatureVerifier({'w':public});worker=Worker('w','https://worker.test/rpc',1)
    server=WorkerServer('w',verifier,'agent',private.sign,system_executables=['/usr/bin/printf'])
    requests=[]
    def transport(endpoint,request,*,timeout):requests.append(request);return server.handle(request)
    authenticate=lambda worker,response:verify_response(worker,response,signatures)
    coordinator=Coordinator([worker],transport,authenticate,verifier,'agent')
    jobs=[Job('j1',('/usr/bin/printf','one'),budget=Budget(cpu_seconds=1)),Job('j2',('/usr/bin/printf','two'),budget=Budget(cpu_seconds=1))]
    results=coordinator.dispatch(jobs,{'w':mint(['worker.execute:w'])})
    assert [(id,response['stdout']) for id,response in results]==[('j1','one'),('j2','two')]
    with pytest.raises(PermissionError):server.handle(requests[0])
    altered=dict(results[0][1]);altered['stdout']='forged'
    assert not verify_response(worker,altered,signatures)
