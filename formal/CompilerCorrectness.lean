import Bisimulation
import RiscvEncoding

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

open OmegaRiscvEncoding
def fields (i : Instruction) : Nat × Nat × Nat × Nat × Nat :=
  match i with
  | .addi rd rs imm => (19,rd.val,0,rs.val,imm.val)
def encodeInstruction (i : Instruction) : List Nat :=
  match i with
  | .addi rd rs imm => bytesLE (encodeAddi rd rs imm)
def inspectInstruction (bytes : List Nat) : Option (Nat × Nat × Nat × Nat × Nat) :=
  (wordLE bytes).map fun w =>
    (opcode w,destination w,function3 w,source w,immediate w)

/-- Every encoded instruction recovers exactly its original opcode/registers/
immediate. This closes the byte-encoding gap for the additive fragment only. -/
theorem instruction_bytes_preserve_fields (i : Instruction) :
    inspectInstruction (encodeInstruction i) = some (fields i) := by
  cases i with
  | addi rd rs imm =>
    simp only [inspectInstruction,encodeInstruction,instruction_bytes_roundtrip,
      Option.map_some,fields]
    obtain ⟨h0,h1,h2,h3,h4⟩ := encode_decode rd rs imm
    change some (opcode (encodeAddi rd rs imm),destination (encodeAddi rd rs imm),
      function3 (encodeAddi rd rs imm),source (encodeAddi rd rs imm),
      immediate (encodeAddi rd rs imm)) = some (19,rd.val,0,rs.val,imm.val)
    rw [h0,h1,h2,h3,h4]

theorem compiled_bytes_preserve_fields (p : Program) :
    ((compile p).map encodeInstruction).map inspectInstruction =
      (compile p).map (fun i => some (fields i)) := by
  simp only [List.map_map,instruction_bytes_preserve_fields,Function.comp_def]
#print axioms instruction_bytes_preserve_fields
#print axioms compiled_bytes_preserve_fields
end OmegaCompilerCorrectness
