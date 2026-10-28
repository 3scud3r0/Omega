import Omega.Refinement
namespace OmegaScheduler
theorem service_decreases (remaining served : Nat) (positive : 0 < served) (bounded : served ≤ remaining) :
    remaining - served < remaining := Nat.sub_lt (positive.trans_le bounded) positive
theorem finite_progress (v : Nat → Nat) (n : Nat)
    (step : ∀ i < n, v (i+1)+1 ≤ v i) : v n + n ≤ v 0 := by
  induction n with
  | zero => simp
  | succ n ih =>
    have previous := ih (fun i hi => step i (Nat.lt_trans hi (Nat.lt_succ_self n)))
    have last := step n (Nat.lt_succ_self n)
    omega
#print axioms service_decreases
#print axioms finite_progress
end OmegaScheduler
