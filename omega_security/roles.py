"""Role assignment belongs to the supervisor; signed decisions bind exact data."""
from dataclasses import dataclass
import math
import re
import time


@dataclass(frozen=True)
class Attestation:
    actor: str
    subject: str
    decision: str
    signature: bytes
    expires: float | None = None

    def __post_init__(self):
        if type(self.actor) is not str or not 0 < len(self.actor) <= 256:
            raise ValueError('Invalid attestation actor')
        if type(self.subject) is not str or not re.fullmatch('[0-9a-f]{64}', self.subject):
            raise ValueError('Invalid attestation subject')
        if self.decision not in ('approve', 'reject') or type(self.signature) is not bytes or not 0 < len(self.signature) <= 1024:
            raise ValueError('Invalid signed decision')
        if self.expires is not None and (type(self.expires) not in (int, float) or not math.isfinite(self.expires) or self.expires <= 0):
            raise ValueError('Invalid attestation expiry')


class Roles:
    def __init__(self, assignments, authenticate):
        self.assignments = {k: frozenset(v) for k, v in assignments.items()}
        self.authenticate = authenticate

    def require(self, attestation, role, subject):
        if type(attestation) is not Attestation or attestation.subject != subject:
            raise PermissionError('Attestation subject mismatch')
        if role not in self.assignments.get(attestation.actor, ()):
            raise PermissionError('Role denied')
        if attestation.expires is not None and time.time() >= attestation.expires:
            raise PermissionError('Attestation expired')
        if self.authenticate(attestation) is not True:
            raise PermissionError('Attestation authentication failed')
        if attestation.decision != 'approve':
            raise PermissionError('Approval absent')

    def promotion(self, subject, proposer, verification, approval):
        self.require(verification, 'verifier', subject)
        self.require(approval, 'promoter', subject)
        if verification.expires is None or approval.expires is None:
            raise PermissionError('Promotion attestations require signed expirations')
        if len({proposer, verification.actor, approval.actor}) != 3:
            raise PermissionError('Independent actors required')
        return True
