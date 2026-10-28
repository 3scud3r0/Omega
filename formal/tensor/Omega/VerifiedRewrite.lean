import TensorKernel
namespace OmegaVerifiedRewrite
open OmegaTensor
def Preserves (f : Expr → Expr) : Prop := ∀ e s,
    eval s (f e) = eval s e ∧ defined s (f e) = defined s e ∧
    ∀ x, eval s (derive (f e) x) = eval s (derive e x)
theorem identity_preserves : Preserves id := by intro e s; exact ⟨rfl,rfl,fun _ => rfl⟩
theorem compose_preserves (f g : Expr → Expr) (hf : Preserves f) (hg : Preserves g) :
    Preserves (fun e => g (f e)) := by
  intro e s
  exact ⟨(hg (f e) s).1.trans (hf e s).1,
    (hg (f e) s).2.1.trans (hf e s).2.1,
    fun x => ((hg (f e) s).2.2 x).trans ((hf e s).2.2 x)⟩
theorem generations_preserve (versions : Nat → Expr → Expr)
    (initial : Preserves (versions 0))
    (step : ∀ n, Preserves (versions n) → Preserves (versions (n+1))) :
    ∀ n, Preserves (versions n) := by intro n; induction n with | zero => exact initial | succ n ih => exact step n ih
#print axioms compose_preserves
#print axioms generations_preserve
end OmegaVerifiedRewrite
