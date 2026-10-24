import TensorKernel

/-! OM-011: checked small-step semantics of the scalar lowered core.
    Surface parsing, tensor lowering and the C implementation are separate
    refinement obligations; this module does not assume their correctness. -/
namespace OmegaOperational
open OmegaTensor

inductive Fault where
  | stackUnderflow
  | divisionByZero
  | fuelExhausted
  deriving Repr, DecidableEq

structure Configuration where
  code : List Instruction
  stack : List ℚ

def liftInstruction (value : Option (List ℚ)) : Except Fault (List ℚ) :=
  match value with
  | some xs => .ok xs
  | none => .error .stackUnderflow

def zeroDenominator : Instruction → List ℚ → Bool
  | .div, b :: _ :: _ => decide (b = 0)
  | _, _ => false

def checkedInstruction (s : Env) (i : Instruction) (xs : List ℚ) : Except Fault (List ℚ) :=
  if zeroDenominator i xs then .error .divisionByZero
  else liftInstruction (instruction s i xs)

/-- One instruction, in source evaluation order. Empty code is terminal. -/
inductive Step (s : Env) : Configuration → Configuration → Prop where
  | instruction (i : Instruction) (rest : List Instruction) (before after : List ℚ)
      (h : checkedInstruction s i before = .ok after) :
      Step s ⟨i :: rest, before⟩ ⟨rest, after⟩

theorem step_deterministic (s : Env) (a b c : Configuration)
    (h₁ : Step s a b) (h₂ : Step s a c) : b = c := by
  cases h₁ with
  | instruction i rest before after h =>
    cases h₂ with
    | instruction _ _ _ other h' =>
      have he : after = other := Except.ok.inj (h.symm.trans h')
      cases he
      rfl

theorem checked_instruction_agrees (s : Env) (i : Instruction) (xs ys : List ℚ)
    (h : checkedInstruction s i xs = .ok ys) : instruction s i xs = some ys := by
  unfold checkedInstruction at h
  split at h
  · simp at h
  · cases he : instruction s i xs <;> simp_all [liftInstruction]

/-- Fuel counts instructions, not rational arithmetic operations or CPU cycles. -/
def run (s : Env) : Nat → Configuration → Except Fault Configuration
  | 0, ⟨[], xs⟩ => .ok ⟨[], xs⟩
  | 0, ⟨_ :: _, _⟩ => .error .fuelExhausted
  | _ + 1, ⟨[], xs⟩ => .ok ⟨[], xs⟩
  | n + 1, ⟨i :: rest, xs⟩ =>
    (checkedInstruction s i xs).bind (fun ys => run s n ⟨rest, ys⟩)

/-- Every successful checked execution agrees with the existing stack model. -/
theorem run_agrees (s : Env) (fuel : Nat) (a b : Configuration)
    (h : run s fuel a = .ok b) :
    b.code = [] ∧ execute s a.code a.stack = some b.stack := by
  induction fuel generalizing a b with
  | zero =>
    cases a with
    | mk code xs =>
      cases code with
      | nil =>
        have hb : Configuration.mk [] xs = b := Except.ok.inj h
        cases hb
        exact ⟨rfl, rfl⟩
      | cons i rest => simp [run] at h
  | succ n ih =>
    cases a with
    | mk code xs =>
      cases code with
      | nil =>
        have hb : Configuration.mk [] xs = b := Except.ok.inj h
        cases hb
        exact ⟨rfl, rfl⟩
      | cons i rest =>
        cases he : checkedInstruction s i xs with
        | error fault => simp [run, he, Except.bind] at h
        | ok ys =>
          have hn : run s n ⟨rest, ys⟩ = .ok b := by simpa [run, he, Except.bind] using h
          obtain ⟨terminal, result⟩ := ih ⟨rest, ys⟩ b hn
          exact ⟨terminal, by simpa [execute, checked_instruction_agrees s i xs ys he] using result⟩

/-- The checked machine returns the denotation of every accepted compiled AST. -/
theorem compiled_checked_result (s : Env) (e : Expr) (xs : List ℚ)
    (fuel : Nat) (b : Configuration)
    (h : run s fuel ⟨compile e, xs⟩ = .ok b) : b.stack = eval s e :: xs := by
  have hs := (run_agrees s fuel ⟨compile e, xs⟩ b h).2
  simpa [compile_sound] using hs.symm

#print axioms step_deterministic
#print axioms checked_instruction_agrees
#print axioms run_agrees
#print axioms compiled_checked_result

end OmegaOperational
