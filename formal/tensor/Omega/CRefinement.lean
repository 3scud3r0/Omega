import Omega.CModel
namespace OmegaFormal
open OmegaTensor
/-- Conditional on the native contract. Discharging it for actual C is a separate obligation. -/
theorem native_compilation_result (backend : NativeContract) (s : Env) (e : Expr) (xs : List ℚ) :
    backend.execute s (compile e) xs = some (eval s e :: xs) := by
  rw [backend.implements]
  exact compile_sound s e xs
end OmegaFormal
