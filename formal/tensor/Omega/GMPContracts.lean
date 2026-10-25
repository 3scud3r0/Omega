import Mathlib.Algebra.Order.Field.Rat
namespace OmegaFormal
structure RationalPrimitive where
  operation : ℚ → ℚ → ℚ
  postcondition : ℚ → ℚ → ℚ → Prop
  sound : ∀ a b, postcondition a b (operation a b)
def exactAddition : RationalPrimitive := ⟨(·+·), fun a b r => r=a+b, fun _ _ => rfl⟩
def exactMultiplication : RationalPrimitive := ⟨(·*·), fun a b r => r=a*b, fun _ _ => rfl⟩
def checkedDivision (a b : ℚ) : Option ℚ := if b=0 then none else some (a/b)
theorem division_nonzero (a b : ℚ) (h : b≠0) : checkedDivision a b=some (a/b) := by
  simp [checkedDivision,h]
end OmegaFormal
