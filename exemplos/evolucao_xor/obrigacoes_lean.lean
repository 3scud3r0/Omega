-- Quatro teoremas decidíveis sobre aritmética inteira. 
-- Instale Lean 4 e execute `lean obrigacoes_lean.lean` para conferir.
namespace Omega
def relu (x : Int) : Int := if x < 0 then 0 else x

theorem xor_00 : ((1 : Int) * relu ((0 : Int)+0) + (-2 : Int) * relu ((0 : Int)+0-1) + (0 : Int) * relu ((0 : Int)+0-2)) = (0 : Int) := by
  decide

theorem xor_01 : ((1 : Int) * relu ((0 : Int)+1) + (-2 : Int) * relu ((0 : Int)+1-1) + (0 : Int) * relu ((0 : Int)+1-2)) = (1 : Int) := by
  decide

theorem xor_10 : ((1 : Int) * relu ((1 : Int)+0) + (-2 : Int) * relu ((1 : Int)+0-1) + (0 : Int) * relu ((1 : Int)+0-2)) = (1 : Int) := by
  decide

theorem xor_11 : ((1 : Int) * relu ((1 : Int)+1) + (-2 : Int) * relu ((1 : Int)+1-1) + (0 : Int) * relu ((1 : Int)+1-2)) = (0 : Int) := by
  decide

end Omega
