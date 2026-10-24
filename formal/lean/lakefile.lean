import Lake
open Lake DSL
package omegaKernel
lean_lib Kernel where
  srcDir := "../../omega_nextorch"
@[default_target]
lean_exe omega_kernel where
  root := `Main
