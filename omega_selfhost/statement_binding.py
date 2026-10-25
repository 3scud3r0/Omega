"""Bind a certificate to the exact requested mathematical statement."""
from .proof_protocol import statement_hash,encode
from .driver import verify_result
def verify(expected,envelope,checker,*,checker_id,dependencies):
    if envelope.get('statement_sha256')!=statement_hash(expected):raise ValueError('Unrelated proof statement')
    if encode(envelope.get('statement'))!=encode(expected):raise ValueError('Statement mismatch')
    if envelope.get('checker')!=checker_id or envelope.get('dependencies')!=sorted(set(dependencies)):raise ValueError('Proof environment mismatch')
    if checker(expected,envelope['certificate']) is not True:raise ValueError('Certificate rejected')
    return True
def native(expected_ir,result):
    if encode(expected_ir)!=encode(result.get('ir')):raise ValueError('Result proves a different program')
    return verify_result(result)
