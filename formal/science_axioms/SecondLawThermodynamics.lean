import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity
import Mathlib.Algebra.Order.BigOperators.Group.Finset

namespace OmegaScience
/-- Nonnegative production is an explicit constitutive hypothesis. -/
theorem entropy_production_sum {n : ℕ} (production : Fin n → ℚ)
    (nonnegative : ∀ i, 0 ≤ production i) : 0 ≤ ∑ i, production i := by
  exact Finset.sum_nonneg (fun i _ => nonnegative i)
theorem carnot_bound (hot cold heat work : ℚ) (hh : 0 < hot) (hc : 0 < cold)
    (entropy : 0 ≤ (heat-work)/cold-heat/hot) : work ≤ heat*(1-cold/hot) := by
  have e := (le_div_iff₀ hc).mp (show heat/hot ≤ (heat-work)/cold by linarith)
  have ht : heat/hot*cold = heat*(cold/hot) := by ring
  rw [ht] at e
  linarith

#print axioms entropy_production_sum

#print axioms carnot_bound
end OmegaScience
