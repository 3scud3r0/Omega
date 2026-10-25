import Omega.AutodiffCorrectness
open OmegaFormal OmegaTensor
example (s : Env) (e : Expr) (x : Nat) : eval s (derive e x) = (dual s (basis x) e).2 := derivative_dual s e x
example (s : Env) (a b : Expr) (x : Nat) : eval s (derive (.mul a b) x) = eval s (derive a x)*eval s b + eval s a*eval s (derive b x) := product_chain s a b x
#print axioms OmegaFormal.derivative_dual
