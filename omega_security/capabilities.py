"""Signed, expiring capability data. Signature authority lives outside the agent.

verify_signature(issuer, payload_bytes, signature_bytes) is supplied by the
trusted supervisor and must authenticate against configured public keys.
"""
from dataclasses import dataclass
import time,math,re
from pathlib import Path
from .encoding import canonical,decode


def _text(value,limit=256):
    return type(value) is str and 0<len(value)<=limit and not any(ord(c)<32 for c in value)


@dataclass(frozen=True)
class Capability:
    payload: bytes
    signature: bytes
    issuer: str
    def claims(self):
        return decode(self.payload,max_bytes=16384,max_nodes=1024,max_depth=8)
class CapabilityVerifier:
    def __init__(self,verify_signature,revocations):self.verify_signature=verify_signature;self.revocations=revocations
    def require(self,token,principal,action,*,path=None,subject=None):
        if type(token) is not Capability:raise PermissionError('Signed capability required')
        if not _text(token.issuer) or not _text(principal) or not _text(action):raise PermissionError('Invalid capability identity/action')
        claim=token.claims();required={'id','principal','actions','root','expires'}
        if type(claim) is not dict or not required<=set(claim)<=required|{'subject'}:raise PermissionError('Unknown capability claims')
        if any(not _text(claim[key]) for key in ('id','principal')):raise PermissionError('Invalid capability identity')
        actions=claim['actions']
        if type(actions) is not list or not 1<=len(actions)<=128 or any(not _text(a) for a in actions) or len(set(actions))!=len(actions):
            raise PermissionError('Explicit unique action list required')
        if not _text(claim['root'],4096) or not Path(claim['root']).is_absolute():raise PermissionError('Absolute capability root required')
        if canonical(claim,max_bytes=16384)!=token.payload:raise PermissionError('Noncanonical capability')
        if type(token.signature) is not bytes or not 0<len(token.signature)<=1024:raise PermissionError('Invalid signature representation')
        if self.verify_signature(token.issuer,token.payload,token.signature) is not True:raise PermissionError('Invalid capability signature')
        if claim['principal']!=principal or action not in actions:raise PermissionError('Capability scope denied')
        if type(claim['expires']) not in (int,float) or not math.isfinite(claim['expires']) or time.time()>=claim['expires']:raise PermissionError('Capability expired')
        if not self.revocations.active(claim['id']):raise PermissionError('Capability revoked')
        if subject is not None or 'subject' in claim:
            if type(subject) is not str or not re.fullmatch('[0-9a-f]{64}',subject) or claim.get('subject')!=subject:
                raise PermissionError('Capability does not authorize this exact subject')
        if path is not None:
            if not Path(path).is_absolute():raise PermissionError('Absolute scoped path required')
            root=Path(claim['root']).resolve(strict=True);target=Path(path).resolve()
            if not target.is_relative_to(root):raise PermissionError('Path outside capability')
        return claim
