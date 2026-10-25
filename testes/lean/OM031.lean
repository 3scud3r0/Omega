import Omega.CRefinement
open OmegaFormal OmegaTensor
-- Deliberately conditional: no implementation of actual C/GMP is invented.
example (backend : NativeContract) (s : Env) (e : Expr) (xs : List ℚ) : backend.execute s (compile e) xs = some (eval s e :: xs) := native_compilation_result backend s e xs
#print axioms OmegaFormal.native_compilation_result
