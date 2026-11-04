import Mathlib.Data.Finset.Card
import Lean.Elab.Tactic.Omega

/-! Static quorum lemmas for n=3f+1 and signatures by 2f+1 distinct members.
Cross-round locking, authenticated network implementation and partial-synchrony
liveness of the complete executable protocol remain refinement obligations. -/
namespace OmegaConsensus
variable {Member Value : Type} [DecidableEq Member]

theorem honest_quorum_intersection (a b bad : Finset Member) (f : Nat)
    (ha : 2*f+1 ≤ a.card) (hb : 2*f+1 ≤ b.card)
    (population_bound : (a ∪ b).card ≤ 3*f+1) (faults : bad.card ≤ f) :
    ∃ member, member ∈ a ∧ member ∈ b ∧ member ∉ bad := by
  by_contra absent
  have subset : a ∩ b ⊆ bad := by
    intro member hm
    by_contra healthy
    exact absent ⟨member,(Finset.mem_inter.mp hm).1,(Finset.mem_inter.mp hm).2,healthy⟩
  have card := Finset.card_le_card subset
  have union := Finset.card_union_add_card_inter a b
  omega

theorem same_round_safety (a b bad : Finset Member) (f : Nat) (left right : Value)
    (ha : 2*f+1 ≤ a.card) (hb : 2*f+1 ≤ b.card)
    (population_bound : (a ∪ b).card ≤ 3*f+1) (faults : bad.card ≤ f)
    (honest_signing : ∀ m, m ∉ bad → m ∈ a → m ∈ b → left=right) : left=right := by
  obtain ⟨member,ma,mb,healthy⟩ := honest_quorum_intersection a b bad f ha hb population_bound faults
  exact honest_signing member healthy ma mb

/-- Availability of an honest quorum after delivery, not a proof that arbitrary
partial-synchrony executions eventually deliver a suitable proposal and votes. -/
theorem quorum_available_with_f_faults (members bad : Finset Member) (f : Nat)
    (population : members.card=3*f+1) (faults : bad.card≤f) :
    2*f+1 ≤ (members\bad).card := by
  have partition := Finset.card_sdiff_add_card_inter members bad
  have bound : (members ∩ bad).card≤bad.card := Finset.card_le_card Finset.inter_subset_right
  omega
#print axioms honest_quorum_intersection
#print axioms same_round_safety
#print axioms quorum_available_with_f_faults
end OmegaConsensus
