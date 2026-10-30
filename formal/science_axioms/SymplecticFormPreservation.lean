import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
theorem verlet_determinant (h : ℚ) :
    (1-h^2/2)*(1-h^2/2)-h*(-h+h^3/4)=1 := by ring
theorem area_form_preserved (a b c d x y u v : ℚ) (det : a*d-b*c=1) :
    (a*x+b*y)*(c*u+d*v)-(c*x+d*y)*(a*u+b*v)=x*v-y*u := by
  calc
    _ = (a*d-b*c)*(x*v-y*u) := by ring
    _ = _ := by rw [det]; ring

#print axioms verlet_determinant

#print axioms area_form_preserved
end OmegaScience
