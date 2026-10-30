import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity
import Mathlib.Data.List.Perm.Basic
import Mathlib.Tactic.Omega

namespace OmegaScience
def walkEdges : List ℕ → List (ℕ × ℕ)
  | [] => []
  | [_] => []
  | a::b::rest => (a,b)::walkEdges (b::rest)
/-- Spelling directed two-letter edges cannot uniquely determine a repeated-genome traversal. -/
theorem distinct_spellings_same_edge_multiset :
    ([0,1,0,2,0] : List ℕ) ≠ [0,2,0,1,0] ∧
    (walkEdges [0,1,0,2,0]).Perm (walkEdges [0,2,0,1,0]) := by decide
theorem traversal_edge_count (vertices : List ℕ) : (walkEdges vertices).length=vertices.length-1 := by
  induction vertices using List.twoStepInduction with
  | empty => rfl
  | singleton a => rfl
  | cons_cons a b rest _ ih =>
      simp only [walkEdges, List.length_cons] at *
      omega

#print axioms distinct_spellings_same_edge_multiset

#print axioms traversal_edge_count
end OmegaScience
