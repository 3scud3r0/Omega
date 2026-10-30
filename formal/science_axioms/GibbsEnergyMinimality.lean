import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity
import Mathlib.Algebra.Order.BigOperators.Group.Finset

namespace OmegaScience
/-- A convex quadratic free-energy surrogate has a global stationary minimizer. -/
theorem quadratic_free_energy_minimum {n : ℕ} (weight linear candidate x : Fin n → ℚ)
    (curvature : ∀ i, 0 ≤ weight i)
    (stationary : ∀ i, 2*weight i*candidate i+linear i=0) :
    (∑ i : Fin n, (weight i*(candidate i)^2+linear i*candidate i)) ≤
    (∑ i : Fin n, (weight i*(x i)^2+linear i*x i)) := by
  apply Finset.sum_le_sum
  intro i _
  have positive := mul_nonneg (curvature i) (sq_nonneg (x i-candidate i))
  have h := stationary i
  have linear_value : linear i = -2*weight i*candidate i := by linarith
  rw [linear_value]
  nlinarith

#print axioms quadratic_free_energy_minimum
end OmegaScience
