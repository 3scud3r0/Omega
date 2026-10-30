import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
def det3 (a b c d e f g h i : ℤ) := a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)
theorem bareiss_sylvester_identity (a b c d e f g h i : ℤ) :
    (a*e-d*b)*(a*i-g*c)-(a*f-d*c)*(a*h-g*b)=a*det3 a b c d e f g h i := by
  unfold det3
  ring
theorem bareiss_three_by_three_divisible (a b c d e f g h i : ℤ) :
    a ∣ (a*e-d*b)*(a*i-g*c)-(a*f-d*c)*(a*h-g*b) := by
  exact ⟨det3 a b c d e f g h i, bareiss_sylvester_identity a b c d e f g h i⟩

#print axioms bareiss_sylvester_identity

#print axioms bareiss_three_by_three_divisible
end OmegaScience
