import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

namespace OmegaScience
/-- Unit-mass unit-spring quadratic oscillator, exact rational midpoint map. -/
theorem quadratic_midpoint_energy (q p h : ℚ) :
    (((1-h^2/4)*q+h*p)/(1+h^2/4))^2 +
    (((1-h^2/4)*p-h*q)/(1+h^2/4))^2 = q^2+p^2 := by
  have hd : 1+h^2/4 ≠ 0 := by nlinarith [sq_nonneg h]
  field_simp [hd] <;> ring
/-- A fixed verified energy equality composes over any finite trace. -/
theorem energy_trace_constant (e : ℕ → ℚ) (step : ∀ n, e (n+1)=e n) (n : ℕ) : e n=e 0 := by
  induction n with
  | zero => rfl
  | succ n ih => exact (step n).trans ih

def midpointPosition (q p h mass spring : ℚ) :=
  ((1-h^2*spring/(4*mass))*q+h*p/mass)/(1+h^2*spring/(4*mass))
def midpointMomentum (q p h mass spring : ℚ) :=
  ((1-h^2*spring/(4*mass))*p-h*spring*q)/(1+h^2*spring/(4*mass))
/-- Exact energy preservation for the parameters of the native midpoint kernel. -/
theorem midpoint_mass_spring_energy (q p h mass spring : ℚ)
    (mass_positive : 0 < mass) (spring_nonnegative : 0 ≤ spring) :
    (midpointMomentum q p h mass spring)^2/(2*mass) +
      spring*(midpointPosition q p h mass spring)^2/2 = p^2/(2*mass)+spring*q^2/2 := by
  unfold midpointPosition midpointMomentum
  have hm : mass ≠ 0 := ne_of_gt mass_positive
  have hn : 0 ≤ h^2*spring/(4*mass) :=
    div_nonneg (mul_nonneg (sq_nonneg h) spring_nonnegative)
      (mul_nonneg (by norm_num) mass_positive.le)
  have hd : 1+h^2*spring/(4*mass) ≠ 0 := by linarith
  have hb : 4*mass+h^2*spring ≠ 0 := by
    have h := mul_nonneg (sq_nonneg h) spring_nonnegative
    nlinarith
  field_simp [hm, hd, hb] <;> ring

#print axioms quadratic_midpoint_energy

#print axioms energy_trace_constant
#print axioms midpoint_mass_spring_energy
end OmegaScience
