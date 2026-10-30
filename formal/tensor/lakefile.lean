import Lake
open Lake DSL
package omegaTensorKernel
require mathlib from git "https://github.com/leanprover-community/mathlib4.git" @ "c44e0c8ee63ca166450922a373c7409c5d26b00b"
lean_lib TensorKernel where
  srcDir := "../../omega_selfhost"
lean_lib ProofPrelude where
  srcDir := "../../omega_selfhost"
lean_lib OperationalSemantics where
  srcDir := "../../omega_selfhost"
lean_lib Omega
lean_lib Tier2 where
  srcDir := ".."
lean_lib Universal where
  srcDir := ".."
lean_lib Native where
  srcDir := ".."
lean_lib ScienceAxioms where
  srcDir := "../science_axioms"
  roots := #[`EnergyConservationTheorem, `SecondLawThermodynamics, `SymplecticFormPreservation, `LorentzInvariance, `QuantumUnitarity, `StoichiometricConservation, `GibbsEnergyMinimality, `MassActionLawDerivation, `NeedlemanWunschOptimality, `DeBruijnEulerianEquivalence, `HardyWeinbergStability, `TaylorErrorBoundTheorem, `NewtonRaphsonConvergence, `BareissDivisionFreeTheorem, `GrahamScanConvexity, `LyapunovAsymptoticStability, `KalmanCovariancePositiveDefinite, `NyquistStabilityCriterion]
lean_lib EngineAxioms where
  srcDir := "../../omega_core/formal"
  roots := #[`HamiltonPrinciple]
@[default_target]
lean_exe omega_tensor_kernel where
  root := `Main
