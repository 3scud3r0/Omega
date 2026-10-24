"""Bounded incremental PID with clamped integral anti-windup."""

import math
from dataclasses import asdict, dataclass


@dataclass
class SparsityPID:
    target: float = 8.0
    coefficient: float = 1e-3
    kp: float = 1e-5
    ki: float = 1e-6
    kd: float = 1e-6
    minimum: float = 1e-5
    maximum: float = 0.1
    integral_limit: float = 1000.0
    integral: float = 0.0
    last_error: float = 0.0

    def __post_init__(self):
        if not 0 <= self.minimum <= self.coefficient <= self.maximum or self.target < 0:
            raise ValueError("Invalid PID bounds or target")

    def update(self, observed_l0):
        if not math.isfinite(observed_l0) or observed_l0 < 0:
            raise ValueError("Observed L0 must be finite and nonnegative")
        error = observed_l0 - self.target
        integral = max(-self.integral_limit, min(self.integral_limit, self.integral + error))
        delta = self.kp * error + self.ki * integral + self.kd * (error - self.last_error)
        proposed = self.coefficient + delta
        # Do not accumulate error that pushes further into saturation.
        if (
            self.minimum <= proposed <= self.maximum
            or (self.coefficient >= self.maximum and error < 0)
            or (self.coefficient <= self.minimum and error > 0)
        ):
            self.integral = integral
        self.coefficient = max(self.minimum, min(self.maximum, proposed))
        self.last_error = error
        return self.coefficient

    def state_dict(self):
        return asdict(self)
