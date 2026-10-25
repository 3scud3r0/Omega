"""Signed, expiring capability data. Signature authority lives outside the agent.

verify_signature(issuer, payload_bytes, signature_bytes) is supplied by the
trusted supervisor and must authenticate against configured public keys.
"""
from dataclasses import dataclass
import json,time,math
from pathlib import Path
@dataclass(frozen=True)
class Capability:
    payload: bytes
    signature: bytes
    issuer: str
    def claims(self):
        if type(self.payload) is not bytes or len(self.payload)>16384:raise ValueError('Capability budget exceeded')
        return json.loads(self.payload)
class CapabilityVerifier:
    def __init__(self,verify_signature,revocations):self.verify_signature=verify_signature;self.revocations=revocations
    def require(self,token,principal,action,*,path=None):
        if type(token) is not Capability:raise PermissionError('Signed capability required')
        if self.verify_signature(token.issuer,token.payload,token.signature) is not True:raise PermissionError('Invalid capability signature')
        claim=token.claims();required={'id','principal','actions','root','expires'}
        if type(claim) is not dict or set(claim)!=required:raise PermissionError('Unknown capability claims')
        canonical=json.dumps(claim,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if canonical!=token.payload:raise PermissionError('Noncanonical capability')
        if claim['principal']!=principal or action not in claim['actions']:raise PermissionError('Capability scope denied')
        if type(claim['expires']) not in (int,float) or not math.isfinite(claim['expires']) or time.time()>=claim['expires']:raise PermissionError('Capability expired')
        if not self.revocations.active(claim['id']):raise PermissionError('Capability revoked')
        if path is not None:
            root=Path(claim['root']).resolve(strict=True);target=Path(path).resolve()
            if not target.is_relative_to(root):raise PermissionError('Path outside capability')
        return claim
