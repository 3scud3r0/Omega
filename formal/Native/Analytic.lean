import Omega.Transcendental
import Mathlib.Analysis.SpecialFunctions.Log.Deriv
import Mathlib.Data.Complex.Trigonometric
namespace OmegaNative
theorem sqrt_enclosure (x lo hi : ℝ) (hx : 0 ≤ x) (hl : 0 ≤ lo) (hh : 0 ≤ hi)
    (lower : lo^2 ≤ x) (upper : x ≤ hi^2) : lo ≤ Real.sqrt x ∧ Real.sqrt x ≤ hi := by
  exact ⟨(Real.le_sqrt hl hx).2 lower,(Real.sqrt_le_left hh).2 upper⟩
theorem small_sin (x : ℝ) (hx : |x| ≤ 1) :
    x-x^3/6-|x|^4*(5/96) ≤ Real.sin x ∧ Real.sin x ≤ x-x^3/6+|x|^4*(5/96) := by
  have h := abs_le.mp (Real.sin_bound hx)
  constructor <;> linarith [h.1,h.2]
theorem small_cos (x : ℝ) (hx : |x| ≤ 1) :
    1-x^2/2-|x|^4*(5/96) ≤ Real.cos x ∧ Real.cos x ≤ 1-x^2/2+|x|^4*(5/96) := by
  have h := abs_le.mp (Real.cos_bound hx)
  constructor <;> linarith [h.1,h.2]
theorem log_ratio_enclosure (z : ℝ) (hz : |z| < 1) (n : Nat) :
    |Real.log ((1+z)/(1-z)) -
      ((∑ i ∈ Finset.range n, z^(i+1)/(i+1)) -
       (∑ i ∈ Finset.range n, (-z)^(i+1)/(i+1)))| ≤
        2*(|z|^(n+1)/(1-|z|)) := by
  have hp := Real.abs_log_sub_add_sum_range_le hz n
  have hn := Real.abs_log_sub_add_sum_range_le (by simpa using hz : |(-z)| < 1) n
  rw [abs_neg] at hn
  have hplus : 0 < 1+z := by have := neg_abs_le z; linarith
  have hminus : 0 < 1-z := by have := le_abs_self z; linarith
  rw [Real.log_div (ne_of_gt hplus) (ne_of_gt hminus)]
  have a := abs_le.mp hp
  have b := abs_le.mp hn
  simp only [sub_neg_eq_add] at b
  apply abs_le.mpr
  constructor <;> linarith [a.1,a.2,b.1,b.2]
#print axioms sqrt_enclosure
#print axioms small_sin
#print axioms small_cos
#print axioms log_ratio_enclosure
end OmegaNative
