import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity
import Mathlib.Analysis.SpecificLimits.Normed

namespace OmegaScience
open Filter
theorem scalar_lyapunov_decrease (a x : ℚ) (gain : a^2<1) (state : x ≠ 0) : (a*x)^2<x^2 := by
  have positive : 0 < x^2 := sq_pos_of_ne_zero state
  nlinarith [mul_pos (sub_pos.mpr gain) positive]
theorem scalar_asymptotic_stability (a x : ℝ) (gain : |a|<1) :
    Tendsto (fun n : ℕ => a^n*x) atTop (nhds 0) := by
  simpa using (tendsto_pow_atTop_nhds_zero_of_abs_lt_one gain).mul_const x

#print axioms scalar_lyapunov_decrease

#print axioms scalar_asymptotic_stability
end OmegaScience
