import ProofPrelude
import Mathlib.Tactic.Linarith
import Mathlib.Data.Real.Sqrt
import Mathlib.Tactic.FieldSimp

syntax "omega_refine" : tactic
macro_rules
  | `(tactic| omega_refine) => `(tactic|
      first
      | (solve | norm_num at * <;> first | assumption | nlinarith | positivity)
      | (solve | simp_all)
      | (solve | norm_num at *; field_simp; ring))

namespace OmegaRefinementKernel
theorem guard_sound (p q : Prop) (proof : p → q) (pre : p) : q := proof pre
theorem vector_norm_bound (xs : List ℚ) (limit : ℝ) (positive : 0 ≤ limit) :
    Real.sqrt ((xs.map (fun x => (x : ℝ)^2)).sum) ≤ limit ↔
    (xs.map (fun x => (x : ℝ)^2)).sum ≤ limit^2 := Real.sqrt_le_left positive
theorem rational_denominator_nonzero (x : ℚ) : x.den ≠ 0 := Rat.den_nz x
#print axioms guard_sound
#print axioms vector_norm_bound
#print axioms rational_denominator_nonzero
end OmegaRefinementKernel
