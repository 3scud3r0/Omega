import Lake
open Lake DSL
package omegaTensorKernel
require mathlib from git "https://github.com/leanprover-community/mathlib4.git" @ "c44e0c8ee63ca166450922a373c7409c5d26b00b"
lean_lib TensorKernel where
  srcDir := "../../omega_selfhost"
@[default_target]
lean_exe omega_tensor_kernel where
  root := `Main
