import Omega.Refinement
namespace OmegaUniversal
inductive Ty where | rational | proposition deriving DecidableEq
inductive Expr : Ty → Type where
 | rational (q : ℚ) : Expr .rational
 | add (a b : Expr .rational) : Expr .rational
 | mul (a b : Expr .rational) : Expr .rational
 | le (a b : Expr .rational) : Expr .proposition
 | conj (a b : Expr .proposition) : Expr .proposition
 | divide (a : Expr .rational) (denominator : {q : ℚ // q ≠ 0}) : Expr .rational
def Value : Ty → Type | .rational => ℚ | .proposition => Prop
def eval : {t : Ty} → Expr t → Value t
 | _, .rational q => q
 | _, .add a b => eval a + eval b
 | _, .mul a b => eval a * eval b
 | _, .le a b => eval a ≤ eval b
 | _, .conj a b => eval a ∧ eval b
 | _, .divide a d => eval a / d.val
theorem type_soundness {t : Ty} (e : Expr t) : ∃ v : Value t, eval e = v := ⟨eval e,rfl⟩
theorem division_defined (a : Expr .rational) (d : {q : ℚ // q ≠ 0}) : d.val ≠ 0 := d.property
theorem quorum_intersection_bound (n f q : Nat) (faults : 3*f < n) (quorum : q=n-f) : n+f < 2*q := by omega
#print axioms type_soundness
#print axioms division_defined
#print axioms quorum_intersection_bound
end OmegaUniversal
