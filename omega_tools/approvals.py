from dataclasses import dataclass
import hashlib,json,time
from threading import RLock
@dataclass(frozen=True)
class Approval:
    actor: str
    action_digest: str
    expires: float
    signature: bytes
class ApprovalGate:
    def __init__(self,authenticate,approvers):self.authenticate=authenticate;self.approvers=frozenset(approvers);self.used=set();self.lock=RLock()
    def digest(self,action):return hashlib.sha256(json.dumps(action,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    def consume(self,action,approval,proposer):
        if type(approval) is not Approval or approval.actor not in self.approvers or approval.actor==proposer:raise PermissionError('Independent approver required')
        digest=self.digest(action)
        if approval.action_digest!=digest or time.time()>=approval.expires or self.authenticate(approval) is not True:raise PermissionError('Approval invalid')
        identity=(approval.actor,approval.signature)
        with self.lock:
            if identity in self.used:raise PermissionError('Approval already consumed')
            self.used.add(identity)
        return digest
