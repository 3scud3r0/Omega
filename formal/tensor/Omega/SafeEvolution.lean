/- Conditional preservation across every finite generation. This theorem does
   not assert that an arbitrary C compiler implements its intended semantics. -/
namespace OmegaEvolution

theorem generations_preserve {Program Meaning : Type} (meaning : Program → Meaning)
    (versions : Nat → Program)
    (step : ∀ n, meaning (versions (n + 1)) = meaning (versions n)) :
    ∀ n, meaning (versions n) = meaning (versions 0) := by
  intro n
  induction n with
  | zero => rfl
  | succ n ih => exact Eq.trans (step n) ih

#print axioms generations_preserve
end OmegaEvolution
