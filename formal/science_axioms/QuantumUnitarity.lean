import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity
import Mathlib.Data.Real.Pi.Bounds

namespace OmegaScience
/-- A two-amplitude real rotation acts on both rational components of Q(i). -/
theorem rational_rotation_unitary (a b x y u v : ℚ) (unit : a^2+b^2=1) :
    (a*x-b*u)^2+(a*y-b*v)^2+(b*x+a*u)^2+(b*y+a*v)^2=x^2+y^2+u^2+v^2 := by
  calc
    _ = (a^2+b^2)*(x^2+y^2+u^2+v^2) := by ring
    _ = _ := by rw [unit]; ring
/-- Coarse constants used by the waveguide/packing/well enclosures. -/
theorem real_pi_enclosed : (3:ℝ) ≤ Real.pi ∧ Real.pi ≤ 4 :=
  ⟨Real.pi_gt_three.le, Real.pi_lt_four.le⟩

#print axioms rational_rotation_unitary

#print axioms real_pi_enclosed
end OmegaScience
