import OperationalSemantics
open OmegaTensor OmegaOperational
deriving instance DecidableEq for Except

def observe (result : Except Fault Configuration) : Except Fault (List ℚ) :=
  result.map (fun c => c.stack)

#guard decide (observe (run (fun _ => 3) 3 ⟨[.load 0, .push 2, .mul], []⟩) = .ok [6])
#guard decide (observe (run (fun _ => 3) 2 ⟨[.load 0, .push 2, .mul], []⟩) = .error .fuelExhausted)
#guard decide (observe (run (fun _ => 0) 0 ⟨[], [7]⟩) = .ok [7])
#guard decide (observe (run (fun _ => 0) 1 ⟨[.div], [0, 2]⟩) = .error .divisionByZero)
#guard decide (observe (run (fun _ => 0) 1 ⟨[.div], [2, 0]⟩) = .ok [0])
#guard decide (observe (run (fun _ => 0) 1 ⟨[.add], [1]⟩) = .error .stackUnderflow)
#guard decide (observe (run (fun _ => 0) 3 ⟨compile (.relu (.neg (.lit (-3)))), []⟩) = .ok [3])
