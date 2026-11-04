import Mathlib.Data.List.Basic
import Mathlib.Data.Nat.Basic

/-! Total compiler for a delimited arithmetic expression AST. The target is
stack IR over RV64 words, not final ELF bytes. This is not preservation for all
Omega programs. Source ASTs may have arbitrary depth, vars and constants. -/
namespace OmegaExpressionCompiler
def wordModulus : Nat := 2^64
inductive Expr where
  | literal : Nat → Expr
  | var : Nat → Expr
  | add : Expr → Expr → Expr
  | mul : Expr → Expr → Expr
def eval (env : Nat → Nat) : Expr → Nat
  | .literal n => n % wordModulus
  | .var v => env v % wordModulus
  | .add a b => (eval env a + eval env b) % wordModulus
  | .mul a b => (eval env a * eval env b) % wordModulus
inductive Instruction where
  | push : Nat → Instruction
  | load : Nat → Instruction
  | add : Instruction
  | mul : Instruction
def step (env : Nat → Nat) : Instruction → List Nat → Option (List Nat)
  | .push n, stack => some (n % wordModulus :: stack)
  | .load v, stack => some (env v % wordModulus :: stack)
  | .add, b::a::stack => some ((a+b)%wordModulus :: stack)
  | .mul, b::a::stack => some ((a*b)%wordModulus :: stack)
  | _, _ => none
def run (env : Nat → Nat) : List Instruction → List Nat → Option (List Nat)
  | [], stack => some stack
  | i::rest, stack => (step env i stack).bind (run env rest)
def compile : Expr → List Instruction
  | .literal n => [.push n]
  | .var v => [.load v]
  | .add a b => compile a ++ compile b ++ [.add]
  | .mul a b => compile a ++ compile b ++ [.mul]
theorem run_append (env : Nat → Nat) (a b : List Instruction) (s : List Nat) :
    run env (a++b) s = (run env a s).bind (run env b) := by
  induction a generalizing s with
  | nil => rfl
  | cons i rest ih =>
    simp only [List.cons_append, run]
    cases step env i s with
    | none => rfl
    | some next => exact ih next
/-- Preservation and stack-frame noninterference for every expression,
environment and pre-existing stack. No enumerated-case or fuel bound. -/
theorem compile_correct (e : Expr) (env : Nat → Nat) (stack : List Nat) :
    run env (compile e) stack = some (eval env e :: stack) := by
  induction e generalizing stack with
  | literal n => rfl
  | var v => rfl
  | add a b ha hb =>
    simp only [compile, run_append, ha, Option.bind_some, hb]
    rfl
  | mul a b ha hb =>
    simp only [compile, run_append, ha, Option.bind_some, hb]
    rfl
/-- Compiled expressions cannot fail because of stack underflow. -/
theorem compiled_progress (e : Expr) (env : Nat → Nat) (stack : List Nat) :
    ∃ result, run env (compile e) stack = some result :=
  ⟨eval env e :: stack, compile_correct e env stack⟩
#print axioms compile_correct
#print axioms compiled_progress
end OmegaExpressionCompiler
