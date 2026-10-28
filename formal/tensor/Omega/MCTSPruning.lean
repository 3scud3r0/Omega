import Omega.Refinement
namespace OmegaMCTS
theorem zero_divisor_invalid (d : ℚ) (zero : d = 0) : ¬ d ≠ 0 := by simp [zero]
theorem interval_excludes_target (x target lower upper : ℚ)
    (range : lower ≤ x ∧ x ≤ upper) (outside : target < lower ∨ upper < target) : x ≠ target := by
  rcases outside with h | h <;> intro equal <;> subst target <;> linarith
theorem proposal_has_no_authority (candidate : α) (safe : α → Prop)
    (checker : safe candidate) : safe candidate := checker
#print axioms zero_divisor_invalid
#print axioms interval_excludes_target
end OmegaMCTS
