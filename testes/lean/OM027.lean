import Omega.Preservation
open OmegaFormal
example (s : TypedState .scalar) : ∃ v : ℚ, (finish s).value = some v := finish_preserves_type s
example (e : Term .scalar) (a b : ℚ) (ha : Evaluates e a) (hb : Evaluates e b) : a=b := evaluated_value_unique ha hb
#print axioms OmegaFormal.finish_preserves_type
