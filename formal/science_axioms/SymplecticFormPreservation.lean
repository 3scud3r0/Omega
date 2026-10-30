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

theorem verlet_mass_spring_determinant (h spring mass : ℚ) (mass_nonzero : mass ≠ 0) :
    (1-h^2*spring/(2*mass))^2-(h/mass)*(-h*spring+h^3*spring^2/(4*mass))=1 := by
  field_simp [mass_nonzero] <;> ring

#print axioms verlet_determinant

#print axioms area_form_preserved
#print axioms verlet_mass_spring_determinant
end OmegaScience
