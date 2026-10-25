import Omega.IRTransformations
open OmegaFormal OmegaTensor
example (f g : Expr → Expr) (hf : TransformCorrect f) (hg : TransformCorrect g) : TransformCorrect (fun e => g (f e)) := compose_correct f g hf hg
#print axioms OmegaFormal.compose_correct
