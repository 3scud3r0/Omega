import TensorKernel
namespace OmegaFormal
open OmegaTensor
def reluSlope (q : ℚ) : ℚ := if 0<q then 1 else 0
theorem slope_at_zero : reluSlope 0=0 := by simp [reluSlope]
theorem slope_positive (q : ℚ) (h : 0<q) : reluSlope q=1 := by simp [reluSlope,h]
theorem slope_negative (q : ℚ) (h : q≤0) : reluSlope q=0 := by
  simp [reluSlope,not_lt.mpr h]
theorem relu_denotation (q : ℚ) : (if 0<q then q else 0)=max 0 q := relu_max q
end OmegaFormal
