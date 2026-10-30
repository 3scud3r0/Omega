import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
def sqrtNewton (x upper : ℚ) := (upper+x/upper)/2
theorem sqrt_newton_residual (x upper : ℚ) (nonzero : upper ≠ 0) :
    (sqrtNewton x upper)^2-x=(upper^2-x)^2/(4*upper^2) := by
  unfold sqrtNewton
  field_simp [nonzero] <;> ring
theorem sqrt_newton_enclosure (x upper : ℚ) (hx : 0 ≤ x) (hu : 0 < upper)
    (bound : x ≤ upper^2) : 0 < sqrtNewton x upper ∧ (sqrtNewton x upper)^2 ≥ x ∧ sqrtNewton x upper ≤ upper := by
  have hz : upper ≠ 0 := ne_of_gt hu
  have hp : 0 ≤ x/upper := div_nonneg hx hu.le
  have hstep : 0 < sqrtNewton x upper := by unfold sqrtNewton; linarith
  have residual := sqrt_newton_residual x upper hz
  have hpositive : 0 ≤ (upper^2-x)^2/(4*upper^2) :=
    div_nonneg (sq_nonneg _) (mul_nonneg (by norm_num) (sq_nonneg _))
  have hdivide : x/upper ≤ upper := (div_le_iff₀ hu).2 (by nlinarith)
  exact ⟨hstep, by linarith, by unfold sqrtNewton; linarith⟩

#print axioms sqrt_newton_residual

#print axioms sqrt_newton_enclosure
end OmegaScience
