import Mathlib.Algebra.Order.Field.Rat
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

namespace OmegaEngines

/-- Two time intervals, fixed endpoints, trapezoidal potential quadrature. -/
def localAction (previous current next h mass spring : ℚ) : ℚ :=
  mass * (current - previous)^2 / (2*h) - h*spring*(previous^2+current^2)/4 +
  mass * (next - current)^2 / (2*h) - h*spring*(current^2+next^2)/4

def discreteEL (previous current next h mass spring : ℚ) : ℚ :=
  mass * (2*current-previous-next)/h - h*spring*current

/-- Exact finite variation, including the second-order term; no minimization
    or continuous-field theorem is silently inferred from stationarity. -/
theorem action_variation (previous current next h mass spring epsilon : ℚ)
    (nonzero_step : h ≠ 0) :
    localAction previous (current+epsilon) next h mass spring =
      localAction previous current next h mass spring +
      epsilon * discreteEL previous current next h mass spring +
      epsilon^2 * (mass/h-h*spring/2) := by
  simp only [localAction, discreteEL, div_eq_mul_inv, mul_inv_rev]
  ring

/-- The implemented quadratic DEL recurrence has zero first variation. -/
theorem recurrence_is_stationary (previous current h mass spring : ℚ)
    (nonzero_step : h ≠ 0) (nonzero_mass : mass ≠ 0) :
    discreteEL previous current (2*current-previous-h^2*spring*current/mass)
      h mass spring = 0 := by
  unfold discreteEL
  field_simp [nonzero_step, nonzero_mass] <;> ring

theorem stationary_action_variation (previous current next h mass spring epsilon : ℚ)
    (nonzero_step : h ≠ 0) (stationary : discreteEL previous current next h mass spring = 0) :
    localAction previous (current+epsilon) next h mass spring =
      localAction previous current next h mass spring + epsilon^2*(mass/h-h*spring/2) := by
  rw [action_variation previous current next h mass spring epsilon nonzero_step, stationary]
  ring

/-- Product of two kick shears and a drift shear, with arbitrary endpoint
    Hessians a,b. Determinant one does not imply energy preservation. -/
theorem verlet_jacobian_determinant (h mass a b : ℚ) (nonzero_mass : mass ≠ 0) :
    (1-h^2*a/(2*mass))*(1-h^2*b/(2*mass)) -
      (h/mass)*(-h*(a+b)/2+h^3*a*b/(4*mass)) = 1 := by
  simp only [div_eq_mul_inv, mul_inv_rev]
  ring

/-- Degree-zero cochains on a canonically oriented triangle satisfy d²=0. -/
theorem triangle_exterior_squared_zero (a b c : ℚ) :
    (b-a)+(c-b)-(c-a) = 0 := by ring

/-- Translation Noether balance, stated off shell with force residual. -/
theorem work_energy_balance (velocity momentumRate partialPosition : ℚ) :
    velocity*momentumRate-partialPosition*velocity =
      velocity*(momentumRate-partialPosition) := by ring

#print axioms action_variation
#print axioms recurrence_is_stationary
#print axioms stationary_action_variation
#print axioms verlet_jacobian_determinant
#print axioms triangle_exterior_squared_zero
#print axioms work_energy_balance
end OmegaEngines
