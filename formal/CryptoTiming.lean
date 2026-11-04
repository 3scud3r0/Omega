import Mathlib.Data.Finset.Card

/-! Branch-free selection and a fixed-work loop model. These theorems do NOT
refine all RV instructions or prove cache/speculation/physical timing security.
Secret-dependent big-integer division is absent from field25519_ct.S, but its
full machine-code noninterference proof and native Ed25519 remain open. -/
namespace OmegaCryptoTiming
def select (bit : Bool) (a b : BitVec 64) : BitVec 64 :=
  let mask := if bit then BitVec.allOnes 64 else 0
  b ^^^ ((a ^^^ b) &&& mask)
theorem select_correct (bit : Bool) (a b : BitVec 64) :
    select bit a b = if bit then a else b := by
  cases bit with
  | false => simp [select]
  | true =>
    change b ^^^ ((a ^^^ b) &&& BitVec.allOnes 64) = a
    rw [BitVec.and_allOnes,BitVec.xor_comm a b,←BitVec.xor_assoc]
    simp

inductive Event where
  | read (limb : Nat)
  | write (limb : Nat)
  | alu
  deriving DecidableEq
def limbTrace : List Event := (List.range 8).flatMap fun i => [.read i,.alu,.write i]
def multiplyTrace (_secret : BitVec 255) : List Event :=
  (List.range 255).flatMap fun _ => limbTrace ++ limbTrace ++ limbTrace
theorem fixed_loop_noninterference (left right : BitVec 255) :
    multiplyTrace left = multiplyTrace right := rfl
#print axioms select_correct
#print axioms fixed_loop_noninterference
end OmegaCryptoTiming
