"""OM-038: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_selfhost.axiom_policy import inspect_output,forbid_admissions

def test_lean_axiom_transcript_requires_expected_theorem_and_allowlist():
    assert inspect_output("'theoremP' depends on axioms: [propext]",['theoremP'])=={'theoremP':['propext']}
    with pytest.raises(ValueError):inspect_output("'unrelated' depends on axioms: []",['theoremP'])
    with pytest.raises(ValueError):inspect_output("'theoremP' depends on axioms: [sorryAx]",['theoremP'])

def test_admission_prefilter_rejects_unapproved_proof_source():
    with pytest.raises(ValueError):forbid_admissions('theorem p : True := by sorry')
