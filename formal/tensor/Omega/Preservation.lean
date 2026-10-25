import Omega.TensorOperational
namespace OmegaFormal
/-- Intrinsically typed core only; not an erasure/lowering theorem for Python or C. -/
structure TypedState (t : Ty) where
  term : Term t
  value : Option (Value t)
def finish {t : Ty} (s : TypedState t) : TypedState t := ⟨s.term, some (denote s.term)⟩
theorem finish_preserves_type {t : Ty} (s : TypedState t) :
    ∃ v : Value t, (finish s).value = some v := by
  exact ⟨denote s.term, rfl⟩
theorem evaluated_value_unique {t : Ty} {e : Term t} {a b : Value t}
    (ha : Evaluates e a) (hb : Evaluates e b) : a=b := by
  exact (evaluation_sound ha).symm.trans (evaluation_sound hb)
end OmegaFormal
