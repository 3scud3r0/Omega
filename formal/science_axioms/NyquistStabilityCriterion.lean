import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
/-- First-order loop L(s)=k/(s+a), unity negative feedback. -/
theorem first_order_closed_pole_stable (a k : ℚ) : -(a+k)<0 ↔ 0<a+k := by constructor <;> intro h <;> linarith
theorem first_order_nyquist_right_halfplane (a k omega : ℚ) (pole : 0<a) (gain : 0≤k) :
    -1 < k*a/(a^2+omega^2) := by
  have positive : 0<a^2+omega^2 := by nlinarith [sq_nonneg omega, sq_pos_of_pos pole]
  have nonnegative : 0 ≤ k*a/(a^2+omega^2) := div_nonneg (mul_nonneg gain pole.le) positive.le
  linarith

#print axioms first_order_closed_pole_stable

#print axioms first_order_nyquist_right_halfplane
end OmegaScience
