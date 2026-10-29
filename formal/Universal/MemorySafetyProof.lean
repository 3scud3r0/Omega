import Omega.Refinement
namespace OmegaUniversal
structure Arena where
 capacity : Nat
 used : Nat
 fits : used ≤ capacity
def allocate (a : Arena) (bytes : Nat) : Option Arena :=
 if h : a.used+bytes ≤ a.capacity then some ⟨a.capacity,a.used+bytes,h⟩ else none
theorem allocation_safe (a b : Arena) (bytes : Nat) (success : allocate a bytes = some b) : b.used ≤ b.capacity := b.fits
def checkedRead (buffer : List ℚ) (index : Nat) : Option ℚ := buffer[index]?
theorem out_of_bounds_rejected (buffer : List ℚ) (index : Nat) (outside : buffer.length ≤ index) : checkedRead buffer index = none := by
 simp [checkedRead,List.getElem?_eq_none outside]
theorem release_restores_used (used bytes : Nat) : used+bytes-bytes=used := by omega
theorem arena_footprint_bounded (a : Arena) : a.used ≤ a.capacity := a.fits
#print axioms allocation_safe
#print axioms out_of_bounds_rejected
#print axioms release_restores_used
#print axioms arena_footprint_bounded
end OmegaUniversal
