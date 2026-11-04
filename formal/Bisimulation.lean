import Mathlib.Data.Nat.Basic
import Mathlib.Data.List.Basic
import Mathlib.Tactic.NormNum

/-! A real, deliberately small RV64 instruction model. Registers are words,
x0 is hardwired to zero, ADDI masks to XLEN, and PC advances by four bytes.
Only nonnegative 12-bit immediates are formalized here. Fetch/decode, memory,
branches, allocator, traps and ELF loader are separate open refinements. -/
namespace RiscvOperational
def modulus : Nat := 2^64
def t0 : Fin 32 := ⟨5,by decide⟩
def zero : Fin 32 := ⟨0,by decide⟩
structure State where
  registers : Nat → Nat
  pc : Nat
inductive Instruction where
  | addi (rd rs : Fin 32) (imm : Fin 2048)
def read (s : State) (r : Fin 32) : Nat :=
  if r.val=0 then 0 else s.registers r.val % modulus
def execute (i : Instruction) (s : State) : State :=
  match i with
  | .addi rd rs imm =>
    ⟨fun r => if rd.val≠0 ∧ r=rd.val then (read s rs+imm.val)%modulus
              else s.registers r, s.pc+4⟩
inductive Step (i : Instruction) : State → State → Prop where
  | instruction (s : State) : Step i s (execute i s)
def run : List Instruction → State → State
  | [], s => s
  | i::rest, s => run rest (execute i s)
def additions (xs : List (Fin 2048)) : List Instruction :=
  xs.map fun x => .addi t0 t0 x
def total (xs : List (Fin 2048)) : Nat := (xs.map Fin.val).sum

theorem read_addi (s : State) (n : Fin 2048) :
    read (execute (.addi t0 t0 n) s) t0 = (read s t0+n.val)%modulus := by
  change ((s.registers 5 % modulus+n.val)%modulus)%modulus =
    (s.registers 5 % modulus+n.val)%modulus
  exact Nat.mod_mod _ _

/-- Pointwise simulation between a source additive fold and actual RV64 ADDI
state transitions. No claim about the general Omega source language. -/
theorem run_additions (xs : List (Fin 2048)) (s : State) :
    read (run (additions xs) s) t0 = (read s t0+total xs)%modulus := by
  induction xs generalizing s with
  | nil =>
    change s.registers 5 % modulus = (s.registers 5 % modulus)%modulus
    exact (Nat.mod_mod _ _).symm
  | cons x xs ih =>
    change read (run (additions xs) (execute (.addi t0 t0 x) s)) t0 = _
    rw [ih,read_addi]
    simp only [total,List.map_cons,List.sum_cons]
    rw [Nat.mod_add_mod,Nat.add_assoc]

theorem step_deterministic (i : Instruction) (a b c : State)
    (h : Step i a b) (k : Step i a c) : b=c := by
  cases h;cases k;rfl
#print axioms run_additions
#print axioms step_deterministic
end RiscvOperational
