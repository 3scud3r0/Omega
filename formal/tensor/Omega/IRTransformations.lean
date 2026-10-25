import TensorKernel
namespace OmegaFormal
open OmegaTensor
def TransformCorrect (f : Expr → Expr) : Prop := ∀ e s, eval s (f e)=eval s e
theorem compose_correct (f g : Expr → Expr) (hf : TransformCorrect f) (hg : TransformCorrect g) :
    TransformCorrect (fun e => g (f e)) := by
  intro e s
  rw [hg, hf]
theorem add_zero_rule (e : Expr) : equivalence (.add e (.lit 0)) e := add_zero e
theorem relu_idempotent_rule (e : Expr) : equivalence (.relu (.relu e)) (.relu e) := relu_idem e
end OmegaFormal
