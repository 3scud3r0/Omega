import Mathlib.Data.Complex.Exponential
import Mathlib.Data.Real.Sqrt
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum

namespace OmegaReal
open scoped BigOperators

theorem constant_mul_bounds (x l u c a b : ℝ) (hx : l ≤ x ∧ x ≤ u)
    (hal : a ≤ c*l) (hau : a ≤ c*u) (hbl : c*l ≤ b) (hbu : c*u ≤ b) :
    a ≤ c*x ∧ c*x ≤ b := by
  by_cases hc : 0 ≤ c
  · exact ⟨hal.trans (mul_le_mul_of_nonneg_left hx.1 hc),
           (mul_le_mul_of_nonneg_left hx.2 hc).trans hbu⟩
  · have hc' : c ≤ 0 := le_of_not_ge hc
    exact ⟨hau.trans (mul_le_mul_of_nonpos_left hx.2 hc'),
           (mul_le_mul_of_nonpos_left hx.1 hc').trans hbl⟩

theorem mul_bounds (x y l u a b low high : ℝ)
    (hx : l ≤ x ∧ x ≤ u) (hy : a ≤ y ∧ y ≤ b)
    (hll : low ≤ l*a) (hlu : low ≤ l*b) (hul : low ≤ u*a) (huu : low ≤ u*b)
    (kll : l*a ≤ high) (klu : l*b ≤ high) (kul : u*a ≤ high) (kuu : u*b ≤ high) :
    low ≤ x*y ∧ x*y ≤ high := by
  have hl := constant_mul_bounds y a b l low high hy hll hlu kll klu
  have hu := constant_mul_bounds y a b u low high hy hul huu kul kuu
  by_cases h : 0 ≤ y
  · exact ⟨hl.1.trans (mul_le_mul_of_nonneg_right hx.1 h),
           (mul_le_mul_of_nonneg_right hx.2 h).trans hu.2⟩
  · have h' : y ≤ 0 := le_of_not_ge h
    exact ⟨hu.1.trans (mul_le_mul_of_nonpos_right hx.2 h'),
           (mul_le_mul_of_nonpos_right hx.1 h').trans hl.2⟩

theorem inv_bounds (x l u : ℝ) (hl : 0 < l) (hx : l ≤ x ∧ x ≤ u) :
    1/u ≤ 1/x ∧ 1/x ≤ 1/l := by
  have hx0 : 0 < x := hl.trans_le hx.1
  exact ⟨one_div_le_one_div_of_le hx0 hx.2,
         one_div_le_one_div_of_le hl hx.1⟩

theorem rsqrt_bounds (x l u a b : ℝ) (hl : 0 < l) (ha : 0 < a) (hb : 0 ≤ b)
    (hx : l ≤ x ∧ x ≤ u) (hal : a^2 ≤ l) (hub : u ≤ b^2) :
    1/b ≤ 1/Real.sqrt x ∧ 1/Real.sqrt x ≤ 1/a := by
  have hx0 : 0 ≤ x := le_of_lt (hl.trans_le hx.1)
  have lower : a ≤ Real.sqrt x := (Real.le_sqrt (le_of_lt ha) hx0).2 (hal.trans hx.1)
  have upper : Real.sqrt x ≤ b := (Real.sqrt_le_left hb).2 (hx.2.trans hub)
  exact inv_bounds (Real.sqrt x) a b ha ⟨lower, upper⟩

theorem exp_interval (x l u a b : ℝ) (hx : l ≤ x ∧ x ≤ u)
    (ha : a ≤ Real.exp l) (hb : Real.exp u ≤ b) :
    a ≤ Real.exp x ∧ Real.exp x ≤ b :=
  ⟨ha.trans (Real.exp_le_exp.mpr hx.1), (Real.exp_le_exp.mpr hx.2).trans hb⟩

theorem exp_double (x l u a b : ℝ) (hl : 0 ≤ l)
    (hx : l ≤ Real.exp x ∧ Real.exp x ≤ u)
    (ha : a ≤ l*l) (hb : u*u ≤ b) :
    a ≤ Real.exp (x+x) ∧ Real.exp (x+x) ≤ b := by
  rw [Real.exp_add]
  have hp := Real.exp_pos x
  exact ⟨ha.trans (mul_le_mul hx.1 hx.1 hl (le_of_lt hp)),
         (mul_le_mul hx.2 hx.2 (le_of_lt hp) (hl.trans (hx.1.trans hx.2))).trans hb⟩

theorem normalized_scale (x d c : ℝ) (hc : c ≠ 0) :
    (c*x)/(c*d) = x/d := by
  rw [mul_div_mul_left _ _ hc]

noncomputable def softmax {n : ℕ} (v : Fin (n+1) → ℝ) (i : Fin (n+1)) : ℝ :=
  Real.exp (v i) / ∑ k, Real.exp (v k)

theorem softmax_order {n : ℕ} (v : Fin (n+1) → ℝ) (i j : Fin (n+1)) :
    softmax v i < softmax v j ↔ v i < v j := by
  have positive : 0 < ∑ k, Real.exp (v k) :=
    Finset.sum_pos (fun k _ => Real.exp_pos (v k)) Finset.univ_nonempty
  rw [softmax, softmax, div_lt_div_iff_of_pos_right positive, Real.exp_lt_exp]

theorem taylor_uniform (x : ℝ) (n : ℕ) (hn : 0 < n) (hx : |x| ≤ 1) :
    |Real.exp x - ∑ m ∈ Finset.range n, x^m / m.factorial| ≤
      (n.succ : ℝ) / ((n.factorial : ℝ) * (n : ℝ)) := by
  have power : |x|^n ≤ 1 := pow_le_one₀ (abs_nonneg x) hx
  have coefficient : 0 ≤ (n.succ : ℝ) / ((n.factorial : ℝ) * (n : ℝ)) :=
    div_nonneg (Nat.cast_nonneg _) (mul_nonneg (Nat.cast_nonneg _) (Nat.cast_nonneg _))
  calc
    _ ≤ |x|^n * ((n.succ : ℝ) / ((n.factorial : ℝ) * (n : ℝ))) := Real.exp_bound hx hn
    _ ≤ 1 * ((n.succ : ℝ) / ((n.factorial : ℝ) * (n : ℝ))) := mul_le_mul_of_nonneg_right power coefficient
    _ = _ := one_mul _

#print axioms mul_bounds
#print axioms inv_bounds
#print axioms rsqrt_bounds
#print axioms exp_interval
#print axioms exp_double
#print axioms normalized_scale
#print axioms softmax_order
#print axioms taylor_uniform
end OmegaReal
