import hashlib
from .actions import prepare
from omega_selfhost.proof_protocol import encode


def verify(policy,state,bundle,*,public_key):
    fields={'payload','subject','program','proof','admission','signature'}
    if type(bundle) is not dict or set(bundle)!=fields:raise ValueError('Unknown proof-carrying action envelope')
    if len(encode(bundle))>8*1024**2:raise ValueError('Action proof byte budget exceeded')
    from cryptography.exceptions import InvalidSignature
    try:public_key.verify(bytes.fromhex(bundle['signature']),encode(bundle['payload']))
    except (InvalidSignature,TypeError,ValueError) as error:raise PermissionError('Invalid action signature') from error
    if hashlib.sha256(encode(bundle['payload'])).hexdigest()!=bundle['subject']:raise ValueError('Action subject mismatch')
    if bundle['payload']['statement']['policy_sha256']!=policy.sha256:raise ValueError('Unrelated policy proof')
    class Capture:
        def sign(self,raw):
            if raw!=encode(bundle['payload']):raise ValueError('Action code, state or postcondition changed')
            return bytes.fromhex(bundle['signature'])
    expected=prepare(policy,state,bundle['payload']['statement']['proposal'],signing_key=Capture())
    if any(expected[k]!=bundle[k] for k in ('program','proof','subject','payload')):raise ValueError('Changed action code or proof')
    return expected['payload']['statement']
