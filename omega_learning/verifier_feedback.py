from dataclasses import dataclass
@dataclass(frozen=True)
class Feedback:
    sample_id: str
    candidate_hash: str
    verifier_id: str
    reward: float
    certificate: object
def reward(sample,candidate,verifier,verifier_id,fingerprint):
    result=verifier(sample,candidate)
    if type(result) is not dict or type(result.get('valid')) is not bool:raise ValueError('Verifier protocol violation')
    return Feedback(sample['id'],fingerprint(candidate),verifier_id,1.0 if result['valid'] else 0.0,result.get('certificate'))
