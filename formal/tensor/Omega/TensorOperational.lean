import Omega.TensorDenotation
namespace OmegaFormal
inductive Evaluates : {t : Ty} → Term t → Value t → Prop where
  | number (q : ℚ) : Evaluates (.number q) q
  | matrix {m n : Nat} (a : Fin m → Fin n → ℚ) : Evaluates (.matrix a) a
  | add {t : Ty} {a b : Term t} {av bv : Value t}
      (ha : Evaluates a av) (hb : Evaluates b bv) : Evaluates (.add a b) (addValue av bv)
  | matmul {m k n : Nat} {a : Term (.matrix m k)} {b : Term (.matrix k n)}
      {av : Value (.matrix m k)} {bv : Value (.matrix k n)}
      (ha : Evaluates a av) (hb : Evaluates b bv) : Evaluates (.matmul a b) (multiply av bv)
  | relu {a : Term .scalar} {v : ℚ} (ha : Evaluates a v) :
      Evaluates (.relu a) (if 0 < v then v else 0)
theorem evaluation_sound {t : Ty} {e : Term t} {v : Value t} (h : Evaluates e v) : denote e = v := by
  induction h <;> simp_all [denote]
theorem evaluation_complete {t : Ty} (e : Term t) : Evaluates e (denote e) := by
  induction e <;> simp only [denote] <;> constructor <;> assumption
end OmegaFormal
