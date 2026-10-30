import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
theorem scalar_kalman_covariance_positive (p r h : ℚ) (prior : 0<p) (noise : 0<r) :
    0 < p*r/(h^2*p+r) := by
  exact div_pos (mul_pos prior noise)
    (add_pos_of_nonneg_of_pos (mul_nonneg (sq_nonneg h) prior.le) noise)
theorem zero_noise_can_destroy_strictness : (1:ℚ)*0/(1^2*1+0)=0 := by norm_num

#print axioms scalar_kalman_covariance_positive

#print axioms zero_noise_can_destroy_strictness
end OmegaScience
