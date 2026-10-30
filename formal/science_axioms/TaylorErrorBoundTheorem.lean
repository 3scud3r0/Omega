import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity
import Native.Analytic

namespace OmegaScience
open scoped BigOperators
theorem exp_remainder_below_epsilon (x epsilon : ℝ) (n : ℕ) (hn : 0<n) (domain : |x|≤1)
    (budget : ((n+1:ℕ):ℝ)/(n.factorial*n) < epsilon) :
    |Real.exp x-∑ i ∈ Finset.range n, x^i/i.factorial| < epsilon := by
  exact (OmegaReal.taylor_uniform x n hn domain).trans_lt budget
theorem log_ratio_remainder (z : ℝ) (hz : |z|<1) (n : ℕ) :
    |Real.log ((1+z)/(1-z)) -
       ((∑ i ∈ Finset.range n, z^(i+1)/(i+1))-
        (∑ i ∈ Finset.range n, (-z)^(i+1)/(i+1)))| ≤
        2*(|z|^(n+1)/(1-|z|)) := OmegaNative.log_ratio_enclosure z hz n

#print axioms exp_remainder_below_epsilon

#print axioms log_ratio_remainder
end OmegaScience
