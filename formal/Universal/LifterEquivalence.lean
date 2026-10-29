import Omega.Refinement
namespace OmegaUniversal
inductive Foreign where
 | input (index : Nat)
 | const (value : ℚ)
 | add (a b : Foreign)
 | sub (a b : Foreign)
 | mul (a b : Foreign)
inductive OmegaIR where
 | variable (index : Nat)
 | literal (value : ℚ)
 | sum (a b : OmegaIR)
 | negate (a : OmegaIR)
 | product (a b : OmegaIR)
def foreignEval (env : Nat → ℚ) : Foreign → ℚ
 | .input n => env n
 | .const q => q
 | .add a b => foreignEval env a + foreignEval env b
 | .sub a b => foreignEval env a - foreignEval env b
 | .mul a b => foreignEval env a * foreignEval env b
def lift : Foreign → OmegaIR
 | .input n => .variable n
 | .const q => .literal q
 | .add a b => .sum (lift a) (lift b)
 | .sub a b => .sum (lift a) (.negate (lift b))
 | .mul a b => .product (lift a) (lift b)
def irEval (env : Nat → ℚ) : OmegaIR → ℚ
 | .variable n => env n
 | .literal q => q
 | .sum a b => irEval env a + irEval env b
 | .negate a => -(irEval env a)
 | .product a b => irEval env a * irEval env b
theorem lift_preserves_semantics (p : Foreign) (env : Nat → ℚ) : irEval env (lift p) = foreignEval env p := by
 induction p <;> simp_all [irEval,lift,foreignEval,sub_eq_add_neg]
-- A model theorem for the explicitly admitted arithmetic fragment. Parsing,
-- modular machine arithmetic, arbitrary C memory and floating point are not
-- smuggled into the statement as universally established assumptions.
#print axioms lift_preserves_semantics
end OmegaUniversal
