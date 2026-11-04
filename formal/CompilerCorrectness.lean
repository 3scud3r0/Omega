import Bisimulation

/-! Compiler correctness for the nonnegative immediate-addition fragment only.
This does not discharge correctness of backend_elf64.omega, spills, parser,
BigRational, loops, tensors, or the generated ELF's bytes. -/
namespace OmegaCompilerCorrectness
open RiscvOperational
structure Program where
  initial : Fin 2048
  increments : List (Fin 2048)
def evaluate (p : Program) : Nat := p.initial.val+total p.increments
def compile (p : Program) : List Instruction :=
  .addi t0 zero p.initial :: additions p.increments
theorem compiler_preservation_modulo (p : Program) (s : State) :
    read (run (compile p) s) t0 = evaluate p % modulus := by
  simp only [compile,run]
  rw [run_additions]
  have initialized : read (execute (.addi t0 zero p.initial) s) t0 = p.initial.val%modulus := by
    change ((0+p.initial.val)%modulus)%modulus = _
    rw [Nat.zero_add,Nat.mod_mod]
  rw [initialized,Nat.mod_add_mod]
  rfl

theorem compiler_preservation_exact (p : Program) (s : State)
    (bounded : evaluate p < modulus) :
    read (run (compile p) s) t0 = evaluate p := by
  rw [compiler_preservation_modulo,Nat.mod_eq_of_lt bounded]
#print axioms compiler_preservation_modulo
#print axioms compiler_preservation_exact
end OmegaCompilerCorrectness
