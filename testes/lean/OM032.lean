import Omega.RuntimeContracts
import Mathlib.Tactic.NormNum
open OmegaFormal
example : checkedDivision 3 0 = none := by simp [checkedDivision]
example : checkedDivision 6 2 = some 3 := by norm_num [checkedDivision]
example (r : Region) : (reset r).used = 0 := reset_empty r
example (r : Region) (n : Nat) (h : ¬ r.used+n ≤ r.limit) : reserve r n=none := reserve_rejects r n h
#print axioms OmegaFormal.division_nonzero
