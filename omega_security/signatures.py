"""Ed25519 verification with supervisor-pinned public keys; no private keys here."""
from dataclasses import asdict
import json
from .encoding import canonical
class SignatureVerifier:
    def __init__(self,public_keys):
        self.public_keys={name:bytes(value) for name,value in public_keys.items()}
        if any(len(key)!=32 for key in self.public_keys.values()):raise ValueError('Ed25519 public keys must be 32 bytes')
    def __call__(self,issuer,payload,signature):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        if issuer not in self.public_keys or type(payload) is not bytes or type(signature) is not bytes or len(signature)!=64:return False
        try:Ed25519PublicKey.from_public_bytes(self.public_keys[issuer]).verify(signature,payload)
        except (InvalidSignature,ValueError):return False
        return True
    def record(self,record):
        values=asdict(record);signature=values.pop('signature');issuer=values.get('actor',values.get('reviewer'))
        payload=canonical(values)
        return self(issuer,payload,signature)
