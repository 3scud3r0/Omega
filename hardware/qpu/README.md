# Bounded rational reference RTL

`gcd_stein.sv` implements iterative binary GCD with ready/valid signals.
`stern_brocot.sv` computes continued-fraction convergents and the boundary
semiconvergent for the closest rational with a bounded denominator, with the
same tie rule as Python's `Fraction.limit_denominator`.
`rational_alu.sv` supports addition, subtraction, multiplication and division.
Numerators use the symmetric signed range; positive denominators and their
configured maximum use the positive signed range. Unrepresentable numerators,
invalid operands and division by zero raise `error`. Approximation raises `irq`
and exports the exact error witness `delta_numerator/delta_denominator`.
Consumers must ignore the numeric output when `error` is asserted.

These are reference circuits with combinational integer dividers, not a timed
pipeline or a manufactured processor. GCD is a separate ready/valid unit; the
ALU's continued-fraction path already reduces its result. There is no claim of
one-cycle physical timing, area, power or formal RTL equivalence. Rational
error proofs in Lean cover the executable mathematical specification; RTL is
checked by co-simulation against that specification.

Install Icarus Verilog using the operating system's authenticated package
manager, then run:

```sh
.venv/bin/python -m pytest -q testes/test_qpu_rtl.py
```

Tests include zero division, register overflow, negative division, zero operands,
nearest-fraction error witnesses, and iterative GCD completion. Widths 8, 16 and
32 are co-simulated with fixed and seeded random cases. The default RTL width is 16.
