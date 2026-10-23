import Mathlib

-- Ômega 1.0: teoremas sobre operações racionais CONCRETAS.
-- A tradução NÃO formaliza a correção dos algoritmos de VJP.
-- Execute `lake env lean` em um projeto Lean 4 com Mathlib.

namespace OmegaExport

theorem coordenada_1_0 : ((1 : ℚ) / 1) = ((1 : ℚ) / 1) - ((1 : ℚ) / 128) * ((0 : ℚ) / 1) := by norm_num
theorem coordenada_1_1 : ((3 : ℚ) / 2) = ((2 : ℚ) / 1) - ((1 : ℚ) / 128) * ((64 : ℚ) / 1) := by norm_num
theorem perda_registrada_1 : ((64 : ℚ) / 1) = ((64 : ℚ) / 1) := by norm_num
theorem monotonia_1 : ((36 : ℚ) / 1) ≤ ((64 : ℚ) / 1) := by norm_num

theorem coordenada_2_0 : ((0 : ℚ) / 1) = ((0 : ℚ) / 1) - ((1 : ℚ) / 256) * ((0 : ℚ) / 1) := by norm_num
theorem coordenada_2_1 : ((119 : ℚ) / 128) = ((1 : ℚ) / 1) - ((1 : ℚ) / 256) * ((18 : ℚ) / 1) := by norm_num
theorem perda_registrada_2 : ((36 : ℚ) / 1) = ((36 : ℚ) / 1) := by norm_num

theorem coordenada_3_0 : ((16385 : ℚ) / 8192) = ((2 : ℚ) / 1) - ((1 : ℚ) / 512) * ((0 : ℚ) / 1) + ((1 : ℚ) / 8192) := by norm_num
theorem coordenada_3_1 : ((-8193 : ℚ) / 8192) = ((-1 : ℚ) / 1) - ((1 : ℚ) / 512) * ((0 : ℚ) / 1) + ((-1 : ℚ) / 8192) := by norm_num
theorem coordenada_3_2 : ((126529 : ℚ) / 131072) = ((1 : ℚ) / 1) - ((1 : ℚ) / 512) * ((4527 : ℚ) / 256) + ((-1 : ℚ) / 8192) := by norm_num
theorem coordenada_3_3 : ((61017 : ℚ) / 65536) = ((1 : ℚ) / 1) - ((1 : ℚ) / 512) * ((4527 : ℚ) / 128) + ((1 : ℚ) / 8192) := by norm_num
theorem perda_registrada_3 : ((2277081 : ℚ) / 65536) = ((2277081 : ℚ) / 65536) := by norm_num

end OmegaExport
