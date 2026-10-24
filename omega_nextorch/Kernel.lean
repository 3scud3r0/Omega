/- Finite Boolean kernel. No Mathlib, additional axioms, sorry, or native_decide. -/
namespace Omega

inductive Expr where
  | lit : Bool → Expr
  | var : Nat → Expr
  | neg : Expr → Expr
  | conj : Expr → Expr → Expr
  | disj : Expr → Expr → Expr
  | xor : Expr → Expr → Expr
  | ite : Expr → Expr → Expr → Expr
  deriving Repr

def eval (env : Nat → Bool) : Expr → Bool
  | .lit b => b
  | .var i => env i
  | .neg a => !(eval env a)
  | .conj a b => eval env a && eval env b
  | .disj a b => eval env a || eval env b
  | .xor a b => xor (eval env a) (eval env b)
  | .ite c lo hi => if eval env c then eval env hi else eval env lo

inductive Instr where
  | push : Bool → Instr
  | load : Nat → Instr
  | neg | conj | disj | xor | ite
  deriving Repr

def step (env : Nat → Bool) : Instr → List Bool → Option (List Bool)
  | .push b, s => some (b :: s)
  | .load i, s => some (env i :: s)
  | .neg, a :: s => some ((!a) :: s)
  | .conj, b :: a :: s => some ((a && b) :: s)
  | .disj, b :: a :: s => some ((a || b) :: s)
  | .xor, b :: a :: s => some ((xor a b) :: s)
  | .ite, hi :: lo :: c :: s => some ((if c then hi else lo) :: s)
  | _, _ => none

def run (env : Nat → Bool) : List Instr → List Bool → Option (List Bool)
  | [], s => some s
  | i :: is, s => (step env i s).bind (run env is)

def compile : Expr → List Instr
  | .lit b => [.push b]
  | .var i => [.load i]
  | .neg a => compile a ++ [.neg]
  | .conj a b => compile a ++ compile b ++ [.conj]
  | .disj a b => compile a ++ compile b ++ [.disj]
  | .xor a b => compile a ++ compile b ++ [.xor]
  | .ite c lo hi => compile c ++ compile lo ++ compile hi ++ [.ite]

theorem run_append (env : Nat → Bool) (a b : List Instr) (s : List Bool) :
    run env (a ++ b) s = (run env a s).bind (run env b) := by
  induction a generalizing s with
  | nil => rfl
  | cons i is ih =>
    simp only [List.cons_append, run]
    cases h : step env i s with
    | none => rfl
    | some t => simpa using ih t

-- Semantic preservation for every expression, environment and initial stack.
theorem compile_correct (env : Nat → Bool) (e : Expr) (s : List Bool) :
    run env (compile e) s = some (eval env e :: s) := by
  induction e generalizing s <;>
    simp_all [compile, run_append, run, step, eval]

-- The checker accepts exactly the evaluations of all explicitly supplied rows.
def check (e : Expr) (rows : List ((Nat → Bool) × Bool)) : Bool :=
  rows.all (fun row => eval row.1 e == row.2)

theorem check_sound (e : Expr) (rows : List ((Nat → Bool) × Bool))
    (h : check e rows = true) :
    ∀ row ∈ rows, eval row.1 e = row.2 := by
  simpa [check, List.all_eq_true] using h

theorem check_complete (e : Expr) (rows : List ((Nat → Bool) × Bool))
    (h : ∀ row ∈ rows, eval row.1 e = row.2) : check e rows = true := by
  simpa [check, List.all_eq_true] using h

-- A certified circuit's compiled program agrees on every certified row.
theorem certified_execution (e : Expr) (rows : List ((Nat → Bool) × Bool))
    (h : check e rows = true) (row) (hm : row ∈ rows) (s : List Bool) :
    run row.1 (compile e) s = some (row.2 :: s) := by
  rw [compile_correct, check_sound e rows h row hm]

#print axioms compile_correct
#print axioms check_sound
#print axioms check_complete
#print axioms certified_execution
end Omega
