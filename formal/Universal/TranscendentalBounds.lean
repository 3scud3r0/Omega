import Native.Analytic
namespace OmegaUniversal
open scoped BigOperators
theorem exp_taylor_error_lt_nano (x : ℝ) (domain : |x| ≤ 1) :
 |Real.exp x - ∑ m ∈ Finset.range 20, x^m/m.factorial| < (1:ℝ)/1000000000 := by
 have h := OmegaReal.taylor_uniform x 20 (by norm_num) domain
 have b : ((21:ℝ)/((20:Nat).factorial*20)) < (1:ℝ)/1000000000 := by norm_num [Nat.factorial]
 exact h.trans_lt b
theorem sqrt_width_bound (x lo hi : ℝ) (hx : 0 ≤ x) (hl : 0 ≤ lo) (hh : 0 ≤ hi)
 (lower : lo^2 ≤ x) (upper : x ≤ hi^2) (width : hi-lo ≤ (1:ℝ)/1000000000) :
 |Real.sqrt x - lo| ≤ (1:ℝ)/1000000000 := by
 have h := OmegaNative.sqrt_enclosure x lo hi hx hl hh lower upper
 rw [abs_of_nonneg (sub_nonneg.mpr h.1)]
 linarith [h.2]
#print axioms exp_taylor_error_lt_nano
#print axioms sqrt_width_bound
end OmegaUniversal
