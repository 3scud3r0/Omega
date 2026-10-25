import TensorKernel
namespace OmegaFormal
open OmegaTensor
/-- Existing syntactic forward/reverse derivative correspondence. Analytic differentiability is not assumed. -/
theorem derivative_dual (s : Env) (e : Expr) (x : Nat) :
    eval s (derive e x) = (dual s (basis x) e).2 := derivative_sound s e x
theorem product_chain (s : Env) (a b : Expr) (x : Nat) :
    eval s (derive (.mul a b) x) = eval s (derive a x)*eval s b + eval s a*eval s (derive b x) := by
  rfl
end OmegaFormal
