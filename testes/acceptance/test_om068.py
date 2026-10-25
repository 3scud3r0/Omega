"""OM-068: executable checks; source delivery, not a recorded pass."""
from omega_coder.patch_review import review

def test_patch_review_blocks_escape_secrets_and_proof_admissions():
    report=review({'../escape':'x','a.txt':'password=secret','formal/F.lean':'theorem t : True := by sorry'})
    assert report['blocked'] and report['requires_independent_review']
    assert {f['reason'] for f in report['findings']} >= {'path escape','possible secret disclosure','proof admission declaration'}
