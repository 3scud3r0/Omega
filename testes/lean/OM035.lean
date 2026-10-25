import Omega.MatrixProofs
open OmegaFormal OmegaTensor
example (m n : Nat) (a : Fin m → Fin n → Expr) : transpose n m (transpose m n a)=a := transpose_twice m n a
example (s : Env) (m k n : Nat) (a : Fin m → Fin k → Expr) (b : Fin k → Fin n → Expr) (i : Fin m) (j : Fin n) : eval s (matmul m k n a b i j)=((List.finRange k).map (fun t => eval s (a i t)*eval s (b t j))).sum := matrix_product_denotation s m k n a b i j
#print axioms OmegaFormal.transpose_twice
