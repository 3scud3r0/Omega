import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
def nwRow (sub : ℕ → ℕ → ℤ) (gap : ℤ) (previous : ℕ → ℤ) (row : ℕ) : ℕ → ℤ
  | 0 => ((row+1:ℕ):ℤ)*gap
  | n+1 => max (previous n+sub row n)
      (max (previous (n+1)+gap) (nwRow sub gap previous row n+gap))
def nwScore (sub : ℕ → ℕ → ℤ) (gap : ℤ) : ℕ → ℕ → ℤ
  | 0, n => (n:ℤ)*gap
  | m+1, n => nwRow sub gap (nwScore sub gap m) m n
inductive NWAlignment (sub : ℕ → ℕ → ℤ) (gap : ℤ) : ℕ → ℕ → ℤ → Prop
  | empty : NWAlignment sub gap 0 0 0
  | delete {m n v} : NWAlignment sub gap m n v → NWAlignment sub gap (m+1) n (v+gap)
  | insert {m n v} : NWAlignment sub gap m n v → NWAlignment sub gap m (n+1) (v+gap)
  | diagonal {m n v} : NWAlignment sub gap m n v → NWAlignment sub gap (m+1) (n+1) (v+sub m n)
theorem nw_zero_col (sub : ℕ → ℕ → ℤ) (gap : ℤ) (m : ℕ) : nwScore sub gap m 0=(m:ℤ)*gap := by
  cases m <;> rfl
theorem nw_succ (sub : ℕ → ℕ → ℤ) (gap : ℤ) (m n : ℕ) :
    nwScore sub gap (m+1) (n+1)=max (nwScore sub gap m n+sub m n)
      (max (nwScore sub gap m (n+1)+gap) (nwScore sub gap (m+1) n+gap)) := rfl
theorem nw_alignment_upper {sub : ℕ → ℕ → ℤ} {gap : ℤ} {m n : ℕ} {v : ℤ}
    (alignment : NWAlignment sub gap m n v) : v ≤ nwScore sub gap m n := by
  induction alignment with
  | empty => simp [nwScore]
  | @delete m n v _ ih =>
      apply (add_le_add_right ih gap).trans
      cases n with
      | zero => simp [nw_zero_col, Nat.cast_add, add_mul]
      | succ n =>
          rw [nw_succ]
          exact (le_max_left _ _).trans (le_max_right _ _)
  | @insert m n v _ ih =>
      apply (add_le_add_right ih gap).trans
      cases m with
      | zero => simp [nwScore, Nat.cast_add, add_mul]
      | succ m =>
          rw [nw_succ]
          exact (le_max_right _ _).trans (le_max_right _ _)
  | @diagonal m n v _ ih =>
      rw [nw_succ]
      exact (add_le_add_right ih _).trans (le_max_left _ _)
theorem nw_score_attainable (sub : ℕ → ℕ → ℤ) (gap : ℤ) (m n : ℕ) :
    NWAlignment sub gap m n (nwScore sub gap m n) := by
  induction m generalizing n with
  | zero =>
      induction n with
      | zero => simpa [nwScore] using (NWAlignment.empty : NWAlignment sub gap 0 0 0)
      | succ n ih =>
          simpa [nwScore, Nat.cast_add, add_mul] using NWAlignment.insert ih
  | succ m ih =>
      induction n with
      | zero =>
          simpa [nw_zero_col, Nat.cast_add, add_mul] using NWAlignment.delete (ih 0)
      | succ n left =>
          rw [nw_succ]
          rcases le_total (nwScore sub gap m n+sub m n)
              (max (nwScore sub gap m (n+1)+gap) (nwScore sub gap (m+1) n+gap)) with h | h
          · rw [max_eq_right h]
            rcases le_total (nwScore sub gap m (n+1)+gap) (nwScore sub gap (m+1) n+gap) with h' | h'
            · rw [max_eq_right h']; exact NWAlignment.insert left
            · rw [max_eq_left h']; exact NWAlignment.delete (ih (n+1))
          · rw [max_eq_left h]; exact NWAlignment.diagonal (ih n)
theorem needleman_wunsch_optimal (sub : ℕ → ℕ → ℤ) (gap : ℤ) (m n : ℕ) :
    NWAlignment sub gap m n (nwScore sub gap m n) ∧
    ∀ v, NWAlignment sub gap m n v → v ≤ nwScore sub gap m n :=
  ⟨nw_score_attainable sub gap m n, fun _ alignment => nw_alignment_upper alignment⟩

#print axioms needleman_wunsch_optimal
end OmegaScience
