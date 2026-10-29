import Tier2.GPUInvariantBridge
import Omega.VerifiedRewrite

namespace OmegaHyper
abbrev Rational := ℚ
abbrev Tensor (α : Type) := List α
abbrev OmegaAST := OmegaTensor.Expr
abbrev Environment := OmegaTensor.Env

def withInputs (env : Environment) (x : Tensor Rational) : Environment :=
  fun i => if i < x.length then x[i]! else env (i-x.length)

def eval_ast (p : OmegaAST) (env : Environment) (x : Tensor Rational) : Rational :=
  OmegaTensor.eval (withInputs env x) p

def SemanticEquivalence (orig opt : OmegaAST) : Prop :=
  ∀ env x, eval_ast orig env x = eval_ast opt env x ∧
    OmegaTensor.defined (withInputs env x) orig = OmegaTensor.defined (withInputs env x) opt ∧
    ∀ v, OmegaTensor.eval (withInputs env x) (OmegaTensor.derive orig v) =
      OmegaTensor.eval (withInputs env x) (OmegaTensor.derive opt v)

theorem compiler_mutation_preserves_semantics
    (orig_ast opt_ast : OmegaAST) (p : SemanticEquivalence orig_ast opt_ast) :
    ∀ (env : Environment) (x : Tensor Rational),
      eval_ast orig_ast env x = eval_ast opt_ast env x := fun env x => (p env x).1

theorem semantic_equivalence_transitive (a b c : OmegaAST)
    (ab : SemanticEquivalence a b) (bc : SemanticEquivalence b c) : SemanticEquivalence a c := by
  intro env x
  exact ⟨(ab env x).1.trans (bc env x).1,
    (ab env x).2.1.trans (bc env x).2.1,
    fun v => ((ab env x).2.2 v).trans ((bc env x).2.2 v)⟩

-- This theorem requires every step's equivalence; bootstrap hash equality
-- alone is deliberately not a proof of arbitrary compiler correctness.
theorem generations_preserve (versions : Nat → OmegaAST)
    (step : ∀ n, SemanticEquivalence (versions n) (versions (n+1))) :
    ∀ n, SemanticEquivalence (versions 0) (versions n) := by
  intro n
  induction n with
  | zero => intro env x; exact ⟨rfl,rfl,fun _ => rfl⟩
  | succ n ih => exact semantic_equivalence_transitive _ _ _ ih (step n)

#print axioms compiler_mutation_preserves_semantics
#print axioms semantic_equivalence_transitive
#print axioms generations_preserve
end OmegaHyper
