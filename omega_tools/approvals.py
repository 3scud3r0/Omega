from dataclasses import dataclass
import hashlib,json,time,math,re
from threading import RLock
from omega_security.encoding import digest as action_digest
@dataclass(frozen=True)
class Approval:
    actor: str
    action_digest: str
    expires: float
    signature: bytes
    def __post_init__(self):
        if type(self.actor) is not str or not self.actor or len(self.actor)>256:raise ValueError('Invalid approval actor')
        if type(self.action_digest) is not str or not re.fullmatch('[0-9a-f]{64}',self.action_digest):raise ValueError('Invalid approval subject')
        if type(self.expires) not in (int,float) or not math.isfinite(self.expires) or self.expires<=0:raise ValueError('Invalid approval expiry')
        if type(self.signature) is not bytes or not 0<len(self.signature)<=1024:raise ValueError('Invalid approval signature')
class ApprovalGate:
    def __init__(self,authenticate,approvers):self.authenticate=authenticate;self.approvers=frozenset(approvers);self.used=set();self.lock=RLock()
    def digest(self,action):return action_digest(action)
    def consume(self,action,approval,proposer):
        if type(approval) is not Approval or approval.actor not in self.approvers or approval.actor==proposer:raise PermissionError('Independent approver required')
        digest=self.digest(action)
        if approval.action_digest!=digest or time.time()>=approval.expires or self.authenticate(approval) is not True:raise PermissionError('Approval invalid')
        identity=(approval.actor,approval.signature)
        with self.lock:
            if identity in self.used:raise PermissionError('Approval already consumed')
            self.used.add(identity)
        return digest
