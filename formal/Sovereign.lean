import Mathlib.Data.Rat.Defs

/-! Specifications for the explicitly delimited scalar core. This is NOT a
proof of the Python assembler, native parser, limb arithmetic, ELF loader, or
the existing full Omega compiler. Those refinement obligations remain open.
Division by zero is an observable fault, not Lean's totalized rational zero. -/
namespace OmegaSovereign
inductive Op where
  | add | sub | mul | div
  deriving DecidableEq, Repr
inductive Expr where
  | lit (n : ℚ)
  | bin (op : Op) (a b : Expr)
  deriving DecidableEq, Repr
def applyOp : Op → ℚ → ℚ → Option ℚ
  | .add, a, b => some (a+b)
  | .sub, a, b => some (a-b)
  | .mul, a, b => some (a*b)
  | .div, a, b => if b=0 then none else some (a/b)
def eval : Expr → Option ℚ
  | .lit n => some n
  | .bin op a b => (eval a).bind fun x => (eval b).bind fun y => applyOp op x y
inductive Instruction where
  | push (n : ℚ)
  | binary (op : Op)
  deriving DecidableEq
def compile : Expr → List Instruction
  | .lit n => [.push n]
  | .bin op a b => compile a ++ compile b ++ [.binary op]
def execute : List Instruction → List ℚ → Option (List ℚ)
  | [], stack => some stack
  | .push n :: code, stack => execute code (n :: stack)
  | .binary op :: code, y :: x :: stack =>
      (applyOp op x y).bind fun v => execute code (v :: stack)
  | .binary _ :: _, _ => none

/-- Compilation preserves both values and division faults, with arbitrary
continuations and surrounding stack. -/
theorem compile_continuation (e : Expr) (code : List Instruction) (stack : List ℚ) :
    execute (compile e ++ code) stack = (eval e).bind (fun x => execute code (x :: stack)) := by
  induction e generalizing code stack with
  | lit n => rfl
  | bin op a b ia ib =>
    simp only [compile, List.append_assoc, ia, ib, List.cons_append, List.nil_append]
    cases ha : eval a with
    | none => simp [eval, ha]
    | some x =>
      cases hb : eval b with
      | none => simp [eval, ha, hb]
      | some y => simp [eval, ha, hb, execute]

theorem compile_correct (e : Expr) :
    execute (compile e) [] = (eval e).map (fun x => [x]) := by
  have h := compile_continuation e [] []
  cases he : eval e <;> simpa [execute, he] using h

/- Prefix token grammar, separate from the native infix surface parser. -/
inductive Token where
  | number (n : ℚ)
  | operator (op : Op)
  deriving DecidableEq
def encode : Expr → List Token
  | .lit n => [.number n]
  | .bin op a b => .operator op :: (encode a ++ encode b)
inductive Parses : List Token → Expr → List Token → Prop where
  | lit (n : ℚ) (rest : List Token) : Parses (.number n :: rest) (.lit n) rest
  | bin (op : Op) (input middle rest : List Token) (a b : Expr)
      (left : Parses input a middle) (right : Parses middle b rest) :
      Parses (.operator op :: input) (.bin op a b) rest

theorem parser_roundtrip (e : Expr) (rest : List Token) : Parses (encode e ++ rest) e rest := by
  induction e generalizing rest with
  | lit n => exact .lit n rest
  | bin op a b ia ib =>
    simpa [encode, List.append_assoc] using
      Parses.bin op (encode a ++ (encode b ++ rest)) (encode b ++ rest) rest a b
        (ia (encode b ++ rest)) (ib rest)

theorem parser_unambiguous {input rest : List Token} {e : Expr}
    (h : Parses input e rest) :
    ∀ {other tail}, Parses input other tail → e=other ∧ rest=tail := by
  induction h with
  | lit n rest => intro other tail h; cases h; exact ⟨rfl,rfl⟩
  | bin op input middle rest a b left right il ir =>
    intro other tail h
    cases h with
    | bin _ _ middle' _ a' b' left' right' =>
      obtain ⟨ha, hm⟩ := il left'
      subst middle'
      obtain ⟨hb, hr⟩ := ir right'
      subst a'; subst b'
      exact ⟨rfl,hr⟩

theorem serialization_injective {a b : Expr} (h : encode a = encode b) : a=b := by
  have left := parser_roundtrip a []
  have right := parser_roundtrip b []
  rw [h] at left
  exact (parser_unambiguous left right).1

#print axioms compile_correct
#print axioms parser_roundtrip
#print axioms parser_unambiguous
#print axioms serialization_injective
end OmegaSovereign
