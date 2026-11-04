# Evidências dos modos cognitivos

Código validado: `a1026c7` (2026-11-04). Alterações posteriores deste relatório
são de documentação/proveniência.

- Regressão completa: **1.453 testes e 138 subtestes aprovados, zero falhas**,
  em 1.605,96 segundos; 5 testes ignorados e 3 avisos.
- Quatro testes ignorados exigem CUDA. O quinto exige o prover indisponível no
  ambiente local; esse caminho foi executado com sucesso no CI CPU.
- Testes dirigidos ao verificador/distribuição após fixar o lockfile: 44
  aprovados e 1 ignorado localmente.
- Verificador Rust: 2 testes aprovados; build estático musl concluído.
- Wheel final instalado em diretório separado: descoberta empírica e reserva de
  cotas verificadas. Distribuição amalgamada: comando empírico executado.

[CI CPU com prova real e ponte cognitiva](https://github.com/3scud3r0/Omega/actions/runs/41927000378)
concluiu o build do prover e do verificador estático, os testes Rust e os testes
de execução, adulteração e recibo gerado pela ponte cognitiva. Nenhum recibo de
desenvolvimento ou prova simulada foi aceito.

O ciclo bicameral padrão do exemplo `omega_cognition/examples/affine.json`, com
uma proposta, executou **299.572 observações IID e 9 casos adversariais**, sem
falhas. A cota superior de falha calculada foi
`0.0000099999909700545590296260241246566177167058850887469265952035685468`
a 95% de confiança, sob as hipóteses de amostragem documentadas. Em seguida,
o Lean 4.19 aceitou o lema e a especialização RV64IM-Linux executou sob QEMU,
produzindo exatamente `1/1`.

Esse relatório local registra `native_emitted`, `kernel_activated: false` e
`zk_verified: false`: aquela execução não configurou o prover. O recibo STARK
real da ponte foi validado separadamente no CI. Os escopos são distintos:
equivalência entre expressões racionais no Lean, execução de uma especialização
RV64 e certificado RV32IM/u32 do adaptador zkVM. Isso não demonstra preservação
do compilador completo nem implantação em hardware físico.

SHA-256 do verificador estático reconstruído localmente:
`b469c3632c036ab19f7c95afed5451e13afa0942fe7d8ad7572adf3f0b571562`.

Os arquivos brutos locais estão em `artifacts/bicameral/`: relatório do ciclo,
fontes e recibos Lean, binários RV64, XML de regressão, resumo de revisão,
wheel e descrição preparada do PR. Os comandos e as fronteiras de confiança
estão em [COGNITIVE_MODES.md](COGNITIVE_MODES.md).
