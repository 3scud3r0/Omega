import Mathlib.Algebra.Order.Field.Rat
namespace OmegaFormal
inductive Ty where
  | scalar
  | matrix (rows cols : Nat)
  deriving DecidableEq
def Value : Ty → Type
  | .scalar => ℚ
  | .matrix m n => Fin m → Fin n → ℚ
def addValue : {t : Ty} → Value t → Value t → Value t
  | .scalar, a, b => a+b
  | .matrix _ _, a, b => fun i j => a i j+b i j
def multiply {m k n : Nat} (a : Value (.matrix m k)) (b : Value (.matrix k n)) : Value (.matrix m n) :=
  fun i j => ((List.finRange k).map (fun x => a i x * b x j)).sum
inductive Term : Ty → Type where
  | number (q : ℚ) : Term .scalar
  | matrix {m n : Nat} (a : Fin m → Fin n → ℚ) : Term (.matrix m n)
  | add {t : Ty} (a b : Term t) : Term t
  | matmul {m k n : Nat} (a : Term (.matrix m k)) (b : Term (.matrix k n)) : Term (.matrix m n)
  | relu (a : Term .scalar) : Term .scalar
end OmegaFormal
