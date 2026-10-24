import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
namespace OmegaTensor
abbrev Env := Nat → ℚ
inductive Expr where
  | lit : ℚ → Expr
  | var : Nat → Expr
  | add : Expr → Expr → Expr
  | neg : Expr → Expr
  | mul : Expr → Expr → Expr
  | div : Expr → Expr → Expr
  | pow : Expr → Nat → Expr
  | relu : Expr → Expr
  | gate : Expr → Expr → Expr
  deriving Repr

def eval (s : Env) : Expr → ℚ
  | .lit q => q
  | .var i => s i
  | .add a b => eval s a + eval s b
  | .neg a => -eval s a
  | .mul a b => eval s a * eval s b
  | .div a b => eval s a / eval s b
  | .pow a n => eval s a ^ n
  | .relu a => if 0 < eval s a then eval s a else 0
  | .gate a b => if 0 < eval s a then eval s b else 0

def defined (s : Env) : Expr → Bool
  | .lit _ | .var _ => true
  | .neg a | .pow a _ | .relu a => defined s a
  | .add a b | .mul a b | .gate a b => defined s a && defined s b
  | .div a b => defined s a && defined s b && decide (eval s b ≠ 0)

def derive : Expr → Nat → Expr
  | .lit _, _ => .lit 0
  | .var i, x => .lit (if i = x then 1 else 0)
  | .add a b, x => .add (derive a x) (derive b x)
  | .neg a, x => .neg (derive a x)
  | .mul a b, x => .add (.mul (derive a x) b) (.mul a (derive b x))
  | .div a b, x => .div (.add (.mul (derive a x) b) (.neg (.mul a (derive b x)))) (.pow b 2)
  | .pow a n, x => if n = 0 then .lit 0 else .mul (.mul (.lit n) (.pow a (n-1))) (derive a x)
  | .relu a, x => .gate a (derive a x)
  | .gate a b, x => .gate a (derive b x)

def dual (s d : Env) : Expr → ℚ × ℚ
  | .lit q => (q, 0)
  | .var i => (s i, d i)
  | .add a b => let u := dual s d a; let v := dual s d b; (u.1 + v.1, u.2 + v.2)
  | .neg a => let u := dual s d a; (-u.1, -u.2)
  | .mul a b => let u := dual s d a; let v := dual s d b;
    (u.1 * v.1, u.2 * v.1 + u.1 * v.2)
  | .div a b => let u := dual s d a; let v := dual s d b;
    (u.1 / v.1, (u.2 * v.1 - u.1 * v.2) / v.1^2)
  | .pow a n => let u := dual s d a; (u.1^n, if n = 0 then 0 else n * u.1^(n-1) * u.2)
  | .relu a => let u := dual s d a; (if 0 < u.1 then u.1 else 0, if 0 < u.1 then u.2 else 0)
  | .gate a b => let u := dual s d a; let v := dual s d b;
    (if 0 < u.1 then v.1 else 0, if 0 < u.1 then v.2 else 0)

def basis (x : Nat) : Env := fun i => if i = x then 1 else 0

theorem dual_value (s d : Env) (e : Expr) : (dual s d e).1 = eval s e := by
  induction e <;> simp_all [dual, eval]

theorem derivative_sound (s : Env) (e : Expr) (x : Nat) :
    eval s (derive e x) = (dual s (basis x) e).2 := by
  induction e <;> simp_all [derive, dual, eval, basis, dual_value, sub_eq_add_neg]
  split <;> simp_all [eval]

def environment (xs : List ℚ) : Env := fun i => xs[i]?.getD 0

def checkGradient (e : Expr) (before grad : List ℚ) : Bool :=
  decide (before.length = grad.length) &&
  (List.range before.length).all (fun i => decide (eval (environment before) (derive e i) = grad[i]!))

theorem gradient_sound (e : Expr) (before grad : List ℚ)
    (h : checkGradient e before grad = true) :
    before.length = grad.length ∧
    ∀ i < before.length, (dual (environment before) (basis i) e).2 = grad[i]! := by
  simpa [checkGradient, List.all_eq_true, List.mem_range, derivative_sound] using h

def updates (before after grad noise : List ℚ) (targets : List Nat) (rate : ℚ) : Bool :=
  (List.range before.length).all (fun i => decide
    (after[i]! = if i ∈ targets then before[i]! - rate * grad[i]! + noise[i]! else before[i]!))

def checkStep (e : Expr) (before after grad noise : List ℚ)
    (targets : List Nat) (rate : ℚ) (monotone : Bool) : Bool :=
  decide (0 < rate) && decide (before.length = after.length) &&
  decide (before.length = noise.length) && checkGradient e before grad &&
  defined (environment before) e && defined (environment after) e &&
  updates before after grad noise targets rate &&
  (!monotone || decide (eval (environment after) e ≤ eval (environment before) e))

theorem step_sound (e : Expr) (before after grad noise : List ℚ)
    (targets : List Nat) (rate : ℚ) (monotone : Bool)
    (h : checkStep e before after grad noise targets rate monotone = true) :
    0 < rate ∧ before.length = after.length ∧ before.length = noise.length ∧
    checkGradient e before grad = true ∧
    defined (environment before) e = true ∧ defined (environment after) e = true ∧
    (∀ i < before.length, after[i]! =
      if i ∈ targets then before[i]! - rate * grad[i]! + noise[i]! else before[i]!) ∧
    (monotone = true → eval (environment after) e ≤ eval (environment before) e) := by
  cases monotone <;> simpa [checkStep, updates, List.all_eq_true, List.mem_range, and_assoc] using h

abbrev Tensor (n : Nat) := Fin n → Expr

def sumExpr : List Expr → Expr
  | [] => .lit 0
  | x :: xs => .add x (sumExpr xs)

theorem eval_sum (s : Env) (xs : List Expr) :
    eval s (sumExpr xs) = (xs.map (eval s)).sum := by
  induction xs <;> simp_all [sumExpr, eval]

def matmul (m k n : Nat) (a : Fin m → Fin k → Expr)
    (b : Fin k → Fin n → Expr) : Fin m → Fin n → Expr := fun i j =>
  sumExpr ((List.finRange k).map (fun t => .mul (a i t) (b t j)))

theorem matmul_semantics (s : Env) (m k n : Nat) (a : Fin m → Fin k → Expr)
    (b : Fin k → Fin n → Expr) (i : Fin m) (j : Fin n) :
    eval s (matmul m k n a b i j) =
      ((List.finRange k).map (fun t => eval s (a i t) * eval s (b t j))).sum := by
  simp [matmul, eval_sum, List.map_map, Function.comp_def, eval]

def transpose (m n : Nat) (a : Fin m → Fin n → Expr) : Fin n → Fin m → Expr :=
  fun j i => a i j

theorem transpose_involution (m n : Nat) (a : Fin m → Fin n → Expr) :
    transpose n m (transpose m n a) = a := rfl

theorem relu_max (q : ℚ) : (if 0 < q then q else 0) = max 0 q := by
  by_cases h : 0 < q
  · simp [h, max_eq_right (le_of_lt h)]
  · simp [h, max_eq_left (le_of_not_gt h)]

def equivalence (a b : Expr) : Prop := ∀ s, eval s a = eval s b

theorem add_zero (a : Expr) : equivalence (.add a (.lit 0)) a := by simp [equivalence, eval]
theorem mul_one (a : Expr) : equivalence (.mul a (.lit 1)) a := by simp [equivalence, eval]
theorem div_one (a : Expr) : equivalence (.div a (.lit 1)) a := by simp [equivalence, eval]
theorem pow_one (a : Expr) : equivalence (.pow a 1) a := by simp [equivalence, eval]
theorem double_neg (a : Expr) : equivalence (.neg (.neg a)) a := by simp [equivalence, eval]
theorem relu_idem (a : Expr) : equivalence (.relu (.relu a)) (.relu a) := by
  intro s
  simp only [eval]
  split <;> simp_all

#print axioms derivative_sound
#print axioms gradient_sound
#print axioms step_sound
#print axioms matmul_semantics
#print axioms relu_idem
inductive Instruction where
  | push : ℚ → Instruction
  | load : Nat → Instruction
  | add | neg | mul | div | relu | gate
  | pow : Nat → Instruction

def instruction (s : Env) : Instruction → List ℚ → Option (List ℚ)
  | .push q, xs => some (q :: xs)
  | .load i, xs => some (s i :: xs)
  | .add, b :: a :: xs => some ((a+b)::xs)
  | .neg, a :: xs => some ((-a)::xs)
  | .mul, b :: a :: xs => some ((a*b)::xs)
  | .div, b :: a :: xs => some ((a/b)::xs)
  | .pow n, a :: xs => some ((a^n)::xs)
  | .relu, a :: xs => some ((if 0<a then a else 0)::xs)
  | .gate, b :: a :: xs => some ((if 0<a then b else 0)::xs)
  | _, _ => none

def execute (s : Env) : List Instruction → List ℚ → Option (List ℚ)
  | [], xs => some xs
  | i :: is, xs => (instruction s i xs).bind (execute s is)

def compile : Expr → List Instruction
  | .lit q => [.push q]
  | .var i => [.load i]
  | .add a b => compile a ++ compile b ++ [.add]
  | .neg a => compile a ++ [.neg]
  | .mul a b => compile a ++ compile b ++ [.mul]
  | .div a b => compile a ++ compile b ++ [.div]
  | .pow a n => compile a ++ [.pow n]
  | .relu a => compile a ++ [.relu]
  | .gate a b => compile a ++ compile b ++ [.gate]

theorem execute_append (s : Env) (a b : List Instruction) (xs : List ℚ) :
    execute s (a ++ b) xs = (execute s a xs).bind (execute s b) := by
  induction a generalizing xs with
  | nil => rfl
  | cons i is ih =>
    simp only [List.cons_append, execute]
    cases h : instruction s i xs with
    | none => rfl
    | some ys => simpa using ih ys

theorem compile_sound (s : Env) (e : Expr) (xs : List ℚ) :
    execute s (compile e) xs = some (eval s e :: xs) := by
  induction e generalizing xs <;> simp_all [compile,execute_append,execute,instruction,eval]

def checkMinimum (candidates : List Nat) (score : Nat → Nat) (selected : Nat) : Bool :=
  decide (selected ∈ candidates) && candidates.all (fun x => decide (score selected ≤ score x))

theorem minimum_sound (candidates : List Nat) (score : Nat → Nat) (selected : Nat)
    (h : checkMinimum candidates score selected = true) :
    selected ∈ candidates ∧ ∀ x ∈ candidates, score selected ≤ score x := by
  simpa [checkMinimum,List.all_eq_true] using h

#print axioms compile_sound
#print axioms minimum_sound

end OmegaTensor
