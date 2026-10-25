import TensorKernel
namespace OmegaFormal
open OmegaTensor
theorem matrix_product_denotation (s : Env) (m k n : Nat)
    (a : Fin m → Fin k → Expr) (b : Fin k → Fin n → Expr) (i : Fin m) (j : Fin n) :
    eval s (matmul m k n a b i j)=
      ((List.finRange k).map (fun t => eval s (a i t)*eval s (b t j))).sum :=
  matmul_semantics s m k n a b i j
theorem transpose_twice (m n : Nat) (a : Fin m → Fin n → Expr) :
    transpose n m (transpose m n a)=a := transpose_involution m n a
end OmegaFormal
