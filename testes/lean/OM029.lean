import Omega.IRTransformations
open OmegaFormal OmegaTensor
example (e : Expr) : equivalence (.add e (.lit 0)) e := add_zero_rule e
example (e : Expr) : equivalence (.relu (.relu e)) (.relu e) := relu_idempotent_rule e
#print axioms OmegaFormal.add_zero_rule
