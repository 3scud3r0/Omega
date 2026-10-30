import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
/-- c=1 and a normalised real boost, with its normalisation stated. -/
theorem lorentz_interval (t x beta gamma : ℚ) (normalisation : gamma^2*(1-beta^2)=1) :
    (gamma*(t-beta*x))^2-(gamma*(x-beta*t))^2=t^2-x^2 := by
  calc
    _ = gamma^2*(1-beta^2)*(t^2-x^2) := by ring
    _ = _ := by rw [normalisation]; ring

#print axioms lorentz_interval
end OmegaScience
