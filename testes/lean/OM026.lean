import Omega.TensorOperational
open OmegaFormal
example : denote (Term.add (.number 2) (.number 3)) = (5 : ℚ) := by rfl
example {t : Ty} (e : Term t) : Evaluates e (denote e) := evaluation_complete e
example {t : Ty} {e : Term t} {v : Value t} (h : Evaluates e v) : denote e = v := evaluation_sound h
#print axioms OmegaFormal.evaluation_sound
