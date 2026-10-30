import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity
import Mathlib.Algebra.Order.BigOperators.Group.Finset

namespace OmegaScience
/-- Any explicitly represented conserved linear quantity is unchanged by a balanced extent. -/
theorem balanced_extent_conserves {n : ℕ} (row amount nu : Fin n → ℚ) (extent : ℚ)
    (balance : (∑ j, row j*nu j)=0) :
    (∑ j, row j*(amount j+extent*nu j))=∑ j, row j*amount j := by
  calc
    _ = (∑ j, row j*amount j)+extent*(∑ j, row j*nu j) := by
      simp only [mul_add, Finset.sum_add_distrib]
      congr 1
      rw [Finset.mul_sum]
      apply Finset.sum_congr rfl
      intro j _
      ring
    _ = _ := by rw [balance]; ring

#print axioms balanced_extent_conserves
end OmegaScience
