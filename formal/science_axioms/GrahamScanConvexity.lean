import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
/-- Supporting halfplanes form a convex rational feasible region. -/
def halfplaneRegion {n : ℕ} (a b c : Fin n → ℚ) (x y : ℚ) := ∀ i, a i*x+b i*y ≤ c i
theorem supporting_halfplanes_convex {n : ℕ} (a b c : Fin n → ℚ) (x y u v t : ℚ)
    (first : halfplaneRegion a b c x y) (second : halfplaneRegion a b c u v)
    (lower : 0 ≤ t) (upper : t ≤ 1) :
    halfplaneRegion a b c (t*x+(1-t)*u) (t*y+(1-t)*v) := by
  intro i
  have h1 := mul_le_mul_of_nonneg_left (first i) lower
  have h2 := mul_le_mul_of_nonneg_left (second i) (show 0 ≤ 1-t by linarith)
  nlinarith

#print axioms supporting_halfplanes_convex
end OmegaScience
