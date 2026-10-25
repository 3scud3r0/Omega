"""External reproduction records authenticate an independent actor and exact artifacts."""
from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class ExternalReview:
    reviewer: str
    artifact_sha256: str
    experiment_sha256: str
    outcome: str
    signature: bytes
class ReproductionGate:
    def __init__(self,developers,reviewers,authenticate):self.developers=frozenset(developers);self.reviewers=frozenset(reviewers);self.authenticate=authenticate
    def accept(self,review,artifact_digest,experiment_digest):
        if type(review) is not ExternalReview or review.reviewer in self.developers or review.reviewer not in self.reviewers:raise PermissionError('Independent configured reviewer required')
        if review.artifact_sha256!=artifact_digest or review.experiment_sha256!=experiment_digest:raise ValueError('Reproduction subject mismatch')
        if self.authenticate(review) is not True or review.outcome!='reproduced':raise PermissionError('Authenticated positive reproduction absent')
        return {'reviewer':review.reviewer,'artifact':artifact_digest,'experiment':experiment_digest,'reproduced':True}
def bundle_manifest(artifacts,commands,environment):
    if any(not isinstance(command,list) or not command or any(not isinstance(arg,str) for arg in command) for command in commands):raise ValueError('Structured argv commands required')
    value={'format':'omega-reproduction-1','artifacts':artifacts,'commands':commands,'environment':environment}
    value['sha256']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return value
