import Omega.Refinement
namespace OmegaNative
theorem append_preserves_prefix {α : Type} (history : List α) (entry : α) :
    (history ++ [entry]).take history.length = history := by simp
theorem append_count {α : Type} (history : List α) (entry : α) :
    (history ++ [entry]).length = history.length+1 := by simp
theorem nonempty_key (key : String) (valid : 0 < key.length) : key ≠ "" := by
  intro empty
  subst key
  simp at valid
theorem released_arena (used capacity bytes : Nat) (fits : used+bytes ≤ capacity) :
    used+bytes-bytes = used ∧ used ≤ capacity := by omega
def energy (x v : ℚ) : ℚ := 2*x^2+(x+v)^2
theorem pendulum_energy_decreases (x v : ℚ) :
    energy (x+v/20) (v+(-x-2*v)/20) - energy x v ≤ -(9/100)*(x^2+v^2) := by
  dsimp [energy]
  nlinarith [sq_nonneg (x-v)]
theorem automatic_admission (correct improved policy : Prop)
    (proof : correct) (gain : improved) (enabled : policy) : correct ∧ improved ∧ policy := ⟨proof,gain,enabled⟩
#print axioms append_preserves_prefix
#print axioms append_count
#print axioms nonempty_key
#print axioms released_arena
#print axioms pendulum_energy_decreases
#print axioms automatic_admission
end OmegaNative
