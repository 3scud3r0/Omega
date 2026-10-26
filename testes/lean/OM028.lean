import Omega.Progress
open OmegaFormal
example {t : Ty} (e : Term t) : ∃ v : Value t, Evaluates e v := progress e
example : ∃ v : ℚ, Evaluates (.relu (.number (-3))) v :=
  progress (Term.relu (Term.number (-3)))
#print axioms OmegaFormal.progress
