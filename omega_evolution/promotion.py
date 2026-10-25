"""Re-authenticate the exact proposal and artifact manifest at activation time."""
from dataclasses import dataclass, asdict
import hashlib
import re
from .proposals import Proposal
from .component_registry import _path
from omega_security.encoding import canonical, decode, digest, snapshot
from omega_security.roles import Attestation


@dataclass(frozen=True)
class PromotionDecision:
    """A data envelope, never authority merely because it was constructed."""
    payload: bytes
    verification: Attestation
    approval: Attestation

    @property
    def subject(self):
        return hashlib.sha256(self.payload).hexdigest()

    @property
    def receipt(self):
        return digest({'subject': self.subject,
                       'verification': self.verification.signature.hex(),
                       'verifier': self.verification.actor,
                       'approval': self.approval.signature.hex(),
                       'promoter': self.approval.actor})


class PromotionGate:
    def __init__(self, roles, registry, verify_artifacts, audit):
        self.roles = roles
        self.registry = registry
        self.verify_artifacts = verify_artifacts
        self.audit = audit

    def prepare(self, proposal, paths, checks, artifacts, *, version=None):
        """Return canonical bytes for independent actors to examine and sign."""
        if type(proposal) is not Proposal:
            raise TypeError('Typed proposal required')
        if type(paths) not in (list, tuple) or not 1 <= len(paths) <= 1024 or any(type(p) is not str for p in paths):
            raise ValueError('Bounded explicit changed paths required')
        if len(set(paths)) != len(paths):
            raise ValueError('Duplicate changed path')
        required = self.registry.require_patch(proposal.component, paths)
        if type(checks) is not dict or any(type(value) is not bool for value in checks.values()):
            raise ValueError('Explicit invariant outcomes required')
        if not set(required) <= set(checks) or any(checks[name] is not True for name in required):
            raise PermissionError('Required invariants failed or missing')
        if type(artifacts) is not dict or not artifacts:
            raise ValueError('Artifact manifest required')
        if artifacts.get('patch_sha256') != proposal.patch_sha256 or artifacts.get('baseline_version') != proposal.baseline_version:
            raise PermissionError('Artifact provenance does not match the proposed patch/baseline')
        if type(artifacts.get('baseline_artifacts_sha256')) is not str or not re.fullmatch('[0-9a-f]{64}', artifacts['baseline_artifacts_sha256']):
            raise ValueError('Baseline artifact manifest digest required')
        if type(artifacts.get('files')) is not dict or not artifacts['files']:
            raise ValueError('Explicit artifact file digests required')
        for path, sha in artifacts['files'].items():
            _path(path)
            if type(sha) is not str or not re.fullmatch('[0-9a-f]{64}', sha):
                raise ValueError('Full artifact byte digests required')
        version = proposal.id if version is None else version
        if type(version) is not str or not 0 < len(version) <= 256:
            raise ValueError('Bounded target version required')
        return canonical({'format': 'omega-promotion-1', 'version': version,
                          'proposal': asdict(proposal), 'paths': sorted(paths),
                          'checks': checks, 'artifacts': artifacts})

    def approve(self, proposal, paths, checks, verification, approval, artifacts, *, version=None):
        payload = self.prepare(proposal, paths, checks, artifacts, version=version)
        decision = PromotionDecision(payload, verification, approval)
        self.authorize(decision, decode(payload)['version'], proposal.baseline_version)
        self.audit.append({'event': 'promotion_authorized', 'subject': decision.subject,
                           'proposal': proposal.id, 'proposer': proposal.proposer,
                           'verifier': verification.actor, 'promoter': approval.actor})
        return decision

    def authorize(self, decision, version, baseline, *, baseline_artifacts_sha256=None):
        """The version store calls this again, inside its activation transaction."""
        if type(decision) is not PromotionDecision or type(decision.verification) is not Attestation or type(decision.approval) is not Attestation:
            raise PermissionError('Authenticated promotion envelope required')
        value = decode(decision.payload)
        fields = {'format', 'version', 'proposal', 'paths', 'checks', 'artifacts'}
        if type(value) is not dict or set(value) != fields or value['format'] != 'omega-promotion-1':
            raise PermissionError('Unknown promotion protocol')
        proposal = Proposal(**value['proposal'])
        expected = self.prepare(proposal, value['paths'], value['checks'], value['artifacts'], version=value['version'])
        if expected != decision.payload or value['version'] != version or proposal.baseline_version != baseline:
            raise PermissionError('Promotion version/baseline binding mismatch')
        if baseline_artifacts_sha256 is not None and value['artifacts']['baseline_artifacts_sha256'] != baseline_artifacts_sha256:
            raise PermissionError('Promotion refers to different baseline artifacts')
        self.roles.promotion(decision.subject, proposal.proposer, decision.verification, decision.approval)
        checked = snapshot(value['artifacts'])
        if self.verify_artifacts(checked) is not True or canonical(checked) != canonical(value['artifacts']):
            raise PermissionError('Artifact verification failed or mutated its input')
        # Artifact callbacks can be slow: do not allow expiry/revocation meanwhile.
        self.roles.promotion(decision.subject, proposal.proposer, decision.verification, decision.approval)
        return {'version': version, 'baseline': baseline, 'proposal': proposal.id,
                'subject': decision.subject, 'receipt': decision.receipt,
                'artifacts_sha256': digest(value['artifacts']), 'promoter': decision.approval.actor}
