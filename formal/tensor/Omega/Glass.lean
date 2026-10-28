import Omega.Refinement
namespace OmegaGlass
theorem threshold_sound (score lower upper threshold : ℚ)
    (bounds : lower ≤ score ∧ score ≤ upper) (margin : threshold < lower) : threshold < score :=
  margin.trans_le bounds.1
theorem orthogonal_axes (x y : ℚ) : x*0 + 0*y = 0 := by ring
theorem concept_requires_grounding (axis : α) (meaning : α → Prop) (proof : meaning axis) : meaning axis := proof
#print axioms threshold_sound
end OmegaGlass
