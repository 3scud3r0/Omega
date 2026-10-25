import OperationalSemantics
namespace OmegaFormal
open OmegaTensor OmegaOperational
/-- Specification boundary: rational abstract states, not machine bytes or GMP limbs. -/
structure NativeContract where
  execute : Env → List Instruction → List ℚ → Option (List ℚ)
  implements : ∀ s code stack, execute s code stack = OmegaTensor.execute s code stack
end OmegaFormal
