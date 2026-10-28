import Omega.Refinement
namespace OmegaLinearMemory
theorem expired_generation (old current : Nat) (changed : old ≠ current) : ¬ old = current := changed
theorem reuse_is_disjoint (startA endA startB endB : Nat)
    (ordered : endA < startB ∨ endB < startA) :
    ¬ ∃ t, startA ≤ t ∧ t ≤ endA ∧ startB ≤ t ∧ t ≤ endB := by
  rcases ordered with h | h <;> rintro ⟨t,a,b,c,d⟩ <;> omega
#print axioms reuse_is_disjoint
end OmegaLinearMemory
