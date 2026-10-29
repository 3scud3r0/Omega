# Validação do Ômega Hyper-Core

Execução em 2026-10-29, Linux x86_64, Python 3.12.14, CUDA SDK 13.4.92,
GCC 14.2 e Lean 4.19.0. O ambiente possui **zero dispositivos CUDA**.

## Comandos e resultados

```sh
bash scripts/setup-cuda.sh
LEAN_NUM_THREADS=4 bash scripts/test.sh -q --junitxml=artifacts/hyper-core-final-tests.xml
LEAN_NUM_THREADS=4 .venv/bin/python -m pytest -q testes/test_hyper_*.py --junitxml=artifacts/hyper-core-targeted-final.xml
.venv/bin/python -m omega hyper benchmark --output artifacts/hyper-gpu-benchmark
```

A suíte completa passou com **883 testes e 37 subtestes**, quatro ignorados,
zero falhas e zero erros. Depois dos ajustes finais, a suíte dos novos fluxos
passou com **19 testes**, dois ignorados, zero falhas e zero erros. Ela inclui
as verificações adicionais de importação limpa e prova dos limites do Tier‑1.
Os JUnits registram 924 casos incluindo subtestes na execução completa e 21 na
execução específica final. Os resultados não devem ser somados como casos únicos.
As três advertências da suíte completa vêm de bibliotecas externas Orange/UMAP.

O benchmark retorna **77 / pending** pela ausência de GPU. Alvos CUDA foram
compilados, incluindo o executável de stress com dez milhões de operações.
A execução desse stress e a meta de cinquenta mil nós em um segundo não foram
realizadas. Os dois testes GPU anteriores também continuam ignorados.
**Não existe medição de filtro em dez nanossegundos nem de milhões de hipóteses
por segundo neste ambiente.** Consulte `hyper-core-gpu.json`.

## Evidência funcional

- ALU compartilhada host/CUDA: dez mil operações racionais comparadas com
  `Fraction`, Stein comparado com `math.gcd`, mil aproximações de grande
  magnitude com testemunha de erro exata, cancelamento antes de overflow e
  traps de divisão por zero. O código host foi instrumentado com UBSan.
- CUDA: kernels completos de avaliação, MCTS, filtro e seleção de elites
  compilados e ligados. A ausência de dispositivo é explícita; a referência
  CPU não é apresentada como execução GPU.
- ASTs e intervalos: lotes SoA comparados à avaliação racional independente,
  ciclos/índices malformados recusados, intervalos contendo zero rejeitados,
  perdas de precisão conservadoras e amostras dentro das caixas conferidas.
- Tier‑2: pool assíncrono, objetos Lean reais, assinatura Ed25519, rejeição de
  metadados/objetos adulterados e contratos falsos. Caixas e limites recebem
  provas independentes; limites falsos e troca de ordem das variáveis são
  exercitados. O contrato original permanece comprovado separadamente.
- Sono: CSE entre dois programas realmente aprovados, geração de rotina nativa
  `.omega`, banco assinado, revalidação e uso da abstração pelo frontend genérico
  com execução nativa. Alteração da definição do banco é recusada.
- Curiosidade: famílias limitadas reprodutíveis por seed, estimativa empírica de
  incerteza, bloqueio por ociosidade e época completa no modo host explícito.
- Evolução: recibo Lean → identidade universal → quatro estágios nativos →
  ponto fixo. O probe caiu de sete para cinco nós e recebeu 21 teoremas.
  Instalação com substituição de fonte e commit foi testada em repositório
  temporário, incluindo recusa de mudanças do usuário e rollback em falha do
  supervisor. Nenhum push de época foi executado.
- Runtime: C freestanding instrumentado executou ramos negativos/positivos reais
  de ReLU. Buffer fixo, sequência, descarte por sobrescrita e overflow dos
  contadores passaram com `-Werror` e UBSan.

Uma geração concreta foi emitida em `artifacts/hyper-core-review`, com
`Candidate.lean`, `Candidate.olean`, certificado assinado e os quatro estágios.
Foi auditada, selecionada como compilador padrão local e usada para compilar
`(x*2)-x`, confirmando `y = 17/3` para `x = 17/3`. A seleção local não substituiu
a fonte versionada nem criou commit automático no repositório do usuário.
Hashes do objeto, fonte, binário e registro de adoção estão em `hyper-core.json`.

Os projetos Lean `Tier2` e `Omega` passaram. Toolkit foi reinstalado pelo script
com hashes fixos; a configuração reutilizável do ambiente foi atualizada.
Wheel, sdist e monólito reproduzível são conferidos na finalização da mudança.

## Fronteiras

A garantia formal é sobre o programa racional e seus contratos declarados.
Não há prova do compilador CUDA/SASS ou da cadeia C inteira, nem latência,
optimalidade, alinhamento ou síntese irrestrita garantidos. As provas dos
teoremas de composição exigem equivalência em cada passo. O repertório de
curiosidade e os templates de mutação são limitados; novas funções são usadas
pelo frontend genérico e não instalam opcodes CUDA arbitrários.

Veja [arquivos, contratos e comandos](../docs/HYPER_CORE.md). Binários, chaves
privadas e JUnits permanecem em caminhos ignorados pelo Git; nenhum segredo é
incluído neste relatório.
