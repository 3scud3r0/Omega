import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
theorem hardy_weinberg_sum (p : ℚ) : p^2+2*p*(1-p)+(1-p)^2=1 := by ring
theorem mendelian_allele_invariant (p : ℚ) : p^2+(2*p*(1-p))/2=p := by ring
theorem hardy_weinberg_nonnegative (p : ℚ) (hp : 0 ≤ p) (hq : p ≤ 1) :
    0 ≤ p^2 ∧ 0 ≤ 2*p*(1-p) ∧ 0 ≤ (1-p)^2 := by
  exact ⟨sq_nonneg _, mul_nonneg (mul_nonneg (by norm_num) hp) (by linarith), sq_nonneg _⟩

#print axioms hardy_weinberg_sum

#print axioms mendelian_allele_invariant

#print axioms hardy_weinberg_nonnegative
end OmegaScience
