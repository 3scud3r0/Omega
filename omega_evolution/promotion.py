"""Promotion authority is external to proposal generation and verification."""
from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class PromotionDecision:
    subject: str
    approved: bool
    promoter: str
class PromotionGate:
    def __init__(self,roles,registry,verify_artifacts,audit):self.roles=roles;self.registry=registry;self.verify_artifacts=verify_artifacts;self.audit=audit
    def approve(self,proposal,paths,checks,verification,approval,artifacts):
        required=self.registry.require_patch(proposal.component,paths)
        if not set(required)<=set(checks) or any(checks[name] is not True for name in required):raise PermissionError('Required invariants failed or missing')
        subject=hashlib.sha256(json.dumps({'proposal':proposal.id,'checks':checks,'artifacts':artifacts},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.roles.promotion(subject,proposal.proposer,verification,approval)
        if self.verify_artifacts(artifacts) is not True:raise PermissionError('Artifact verification failed')
        self.audit.append({'subject':subject,'proposal':proposal.id,'proposer':proposal.proposer,'verifier':verification.actor,'promoter':approval.actor,'decision':'approve'})
        return PromotionDecision(proposal.id,True,approval.actor)
