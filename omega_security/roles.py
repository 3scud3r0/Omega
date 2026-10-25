"""Role assignment is supervisor configuration, never candidate-supplied data."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Attestation:
    actor: str
    subject: str
    decision: str
    signature: bytes
class Roles:
    def __init__(self,assignments,authenticate):self.assignments={k:frozenset(v) for k,v in assignments.items()};self.authenticate=authenticate
    def require(self,attestation,role,subject):
        if type(attestation) is not Attestation or attestation.subject!=subject:raise PermissionError('Attestation subject mismatch')
        if role not in self.assignments.get(attestation.actor,()):raise PermissionError('Role denied')
        if self.authenticate(attestation) is not True:raise PermissionError('Attestation authentication failed')
        if attestation.decision!='approve':raise PermissionError('Approval absent')
    def promotion(self,subject,proposer,verification,approval):
        self.require(verification,'verifier',subject);self.require(approval,'promoter',subject)
        if len({proposer,verification.actor,approval.actor})!=3:raise PermissionError('Independent actors required')
        return True
