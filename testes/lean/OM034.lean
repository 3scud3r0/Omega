import Omega.Subgradients
import Mathlib.Tactic.NormNum
open OmegaFormal
example : reluSlope 0=0 := slope_at_zero
example : reluSlope (-1)=0 := slope_negative (-1) (by norm_num)
example : reluSlope 1=1 := slope_positive 1 (by norm_num)
#print axioms OmegaFormal.slope_at_zero
