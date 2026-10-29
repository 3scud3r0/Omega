import Omega.Refinement

namespace OmegaHyper
structure RationalInterval where
  lower : ℚ
  upper : ℚ
  ordered : lower ≤ upper

def Contains (i : RationalInterval) (x : ℚ) : Prop := i.lower ≤ x ∧ x ≤ i.upper

theorem interval_add_sound (a b : RationalInterval) (x y : ℚ)
    (hx : Contains a x) (hy : Contains b y) :
    a.lower + b.lower ≤ x + y ∧ x + y ≤ a.upper + b.upper := by
  constructor <;> linarith [hx.1,hx.2,hy.1,hy.2]

theorem interval_excludes_zero (a : RationalInterval) (x : ℚ)
    (hx : Contains a x) (excluded : a.upper < 0 ∨ 0 < a.lower) : x ≠ 0 := by
  rcases excluded with h | h <;> intro zero <;> rw [zero] at hx <;> linarith [hx.1,hx.2]

-- The GPU bit is advisory. It is never a premise sufficient to establish P.
-- Generated concrete Tier-2 obligations must independently provide checked P.
theorem tier2_admission (_gpu_survivor : Bool) (P : Prop) (checked : P) : P := checked
theorem no_authority_from_a_bit : ¬ (∀ (P : Prop), true = true → P) := by
  intro unsound
  exact unsound False rfl

#print axioms interval_add_sound
#print axioms interval_excludes_zero
#print axioms tier2_admission
#print axioms no_authority_from_a_bit
end OmegaHyper
