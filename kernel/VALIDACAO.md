# Validação executada — Ômega Kernel

Arquivo final: `omega_kernel.omega`, **18,679 linhas**, 64 fontes,
SHA-256 `00693efaa399b7a087a4cfc009b3306c7126ab9926c94fcd94a55838fb821e06`.
A contagem inclui código Ômega ligado, módulos originais, C, Python, testes e
dependências reutilizadas. A sobreposição entre módulos e prefixo está declarada
no manifesto; não representa 18 mil linhas de algoritmos novos.

## Resultados reais

- Regressão completa: **1268 passed, 4 skipped, 3 warnings, 138 subtests passed in 1467.32s (0:24:27)**.
- Ambos os projetos Lean e os módulos científicos/engines foram compilados.
- A suíte integral inclui 27 testes principais do novo kernel.
- Após os ajustes de distribuição: **20 passed, 21 subtests passed in 39.06s**.
- Os hashes dos 21 arquivos de execução e do prefixo Ômega permaneceram idênticos
  aos da suíte integral. Os últimos ajustes trataram a contagem de fontes novas
  e a entrega de `omega_kernel.omega` pela distribuição antiga.
- 135 execuções adicionais nas três ISAs concordaram com um oráculo de inteiros
  independente, incluindo limites assinados, divisão exata e overflow.
- O arquivo misto completo foi compilado pelo bootstrap auditável; seu prefixo
  aceitou a prova de exemplo e emitiu um ELF que retornou `-40` no sandbox.
- Foram executados fuzzing de 20.000 entradas JSON, 2.000 arenas de termos,
  batches diferenciais, ASan/UBSan, reverse mode, adulteração de certificados,
  limites, extração e instalação offline de wheel sem Torch.
- CLI: prova C, prova Ômega, certificado matricial, checagem independente e
  compilação/execução do exemplo funcionaram.

Os quatro testes pulados exigem CUDA. A validação física ARM/RISC-V e o caminho
NEON dos tensores permanecem pendentes; QEMU não substitui esses testes.
Os três avisos da suíte são de depreciação Orange e configuração UMAP.

## Medição de GEMM

CPU: `AMD EPYC 9V74 80-Core Processor`. Compilador: `cc (Debian 14.2.0-19) 14.2.0`.
Comparação no mesmo processo, com alocação e normalização de saída incluídas,
contra multiplicar/somar `mpq` elemento a elemento. Parsing, bootstrap e
compilação ficam fora desta medição. Resultados foram comparados exatamente.

| Entradas | Dimensão | Razão mediana mpq/grid, 3 execuções |
| --- | --- | --- |
| compact-simd | 32 × 32 | 104.33× |
| compact-simd | 64 × 64 | 156.30× |
| wide-gmp | 32 × 32 | 9.02× |
| wide-gmp | 64 × 64 | 8.33× |

São entradas sintéticas pequenas: o primeiro regime favorece o caminho AVX-512;
o segundo usa inteiros de 96 bits e denominadores primos no fallback GMP.
Esses números não representam throughput de redes neurais completas,
matrizes arbitrárias, GPU ou NEON e não estabelecem um ganho universal.

## Reprodução

```sh
export OMEGA_KERNEL_QEMU_AARCH64=/caminho/qemu-aarch64
export OMEGA_KERNEL_QEMU_RISCV64=/caminho/qemu-riscv64
bash scripts/test.sh -q --junitxml=artifacts/kernel-full-final.xml
python -m pytest testes/kernel -q
python scripts/validate-kernel-isa.py --output artifacts/kernel/isa.json
python scripts/benchmark-kernel.py --output artifacts/kernel/benchmark.json
python -m omega_kernel.amalgamation --check
```

Relatórios e hashes estão em `kernel/evidencias/`. O JUnit completo e os logs
locais estão em `artifacts/kernel-full-final.*`; a CI publica seus próprios
artefatos quando executada. Não se afirma aprovação da matriz GitHub Actions
sem uma execução remota.

## Falhas corrigidas e limites

A primeira compilação monolítica esgotou a memória do compilador atual. O build
agora processa grupos de funções completas antes de reunir uma unidade C.
O teste AArch64 encontrou um opcode incorreto na checagem de multiplicação;
o encoding foi corrigido e os casos foram repetidos. Rodadas preliminares
interrompidas não foram usadas como evidência de aprovação.

O verificador implementa MLTT predicativa limitada, sem axiomas declarados.
A correção global dele ainda não foi formalmente demonstrada. Não importa
qualquer certificado Lean, não implementa CIC completo e não altera o portão
Lean existente. Os certificados matriciais provam resultados particulares.
O backend direto suporta o fragmento puro i64 descrito no README.
Não se declara conclusão das 150 tarefas do roteiro com esta entrega.

## Publicação

A implementação inicial foi enviada em `fd6693e`, antes de executar os testes.
A branch é `feat/omega-kernel-amalgamation`; não houve merge ou promoção.
A tentativa de criar PR recebeu `Forbidden` em `api.github.com/graphql`,
bloqueado pela política de rede deste ambiente. Não existe número de PR para
esta entrega enquanto essa abertura não for concluída.
