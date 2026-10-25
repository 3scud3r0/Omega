import Omega.GMPContracts
namespace OmegaFormal
structure Region where
  limit : Nat
  used : Nat
  bounded : used ≤ limit
def reserve (r : Region) (bytes : Nat) : Option Region :=
  if h : r.used+bytes ≤ r.limit then some ⟨r.limit,r.used+bytes,h⟩ else none
theorem reserve_rejects (r : Region) (bytes : Nat) (h : ¬ r.used+bytes ≤ r.limit) : reserve r bytes=none := by
  simp [reserve,h]
def reset (r : Region) : Region := ⟨r.limit,0,Nat.zero_le _⟩
theorem reset_empty (r : Region) : (reset r).used=0 := rfl
end OmegaFormal
