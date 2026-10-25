import Omega.Preservation
namespace OmegaFormal
/-- Total big-step progress of the finite pure core; no loops or division. -/
theorem progress {t : Ty} (e : Term t) : ∃ v : Value t, Evaluates e v :=
  ⟨denote e, evaluation_complete e⟩
end OmegaFormal
