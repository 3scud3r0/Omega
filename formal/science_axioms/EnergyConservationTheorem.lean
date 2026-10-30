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

#print axioms quadratic_midpoint_energy

#print axioms energy_trace_constant
end OmegaScience
