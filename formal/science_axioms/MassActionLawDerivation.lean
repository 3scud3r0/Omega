import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity
import Mathlib.Analysis.SpecialFunctions.Log.Basic

namespace OmegaScience
/-- Two ideal activities; chemical-potential model and equilibrium are explicit. -/
theorem ideal_two_species_mass_action (a b rt muA muB : ℝ)
    (ha : 0 < a) (hb : 0 < b) (hrt : rt ≠ 0)
    (equilibrium : muA+rt*Real.log a=muB+rt*Real.log b) :
    Real.log (b/a)=(muA-muB)/rt := by
  rw [Real.log_div (ne_of_gt hb) (ne_of_gt ha)]
  apply (eq_div_iff hrt).2
  nlinarith

#print axioms ideal_two_species_mass_action
end OmegaScience
