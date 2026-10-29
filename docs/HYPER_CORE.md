# Ômega Hyper-Core

O Hyper-Core separa pesquisa numérica e admissão formal. CUDA produz propostas
em buffers de tamanho fixo; o host reconstrói as ASTs, confere exemplos e
intervalos e exige provas Lean sobre racionais antes de autorizar uma geração.
A ausência de GPU é um resultado explícito, sem substituição silenciosa por CPU.

## Arquivos e contratos

| Arquivos | Implementação |
| --- | --- |
| `hardware/cuda/rational_types.cuh` | ABI alinhada de Rational64/128, status explícitos e limite simétrico int64 |
| `hardware/cuda/rational_alu.cuh` | Operações verificadas contra overflow, Stein, frações contínuas/Stern–Brocot e testemunha racional do erro |
| `hardware/cuda/flat_ast_eval.{cuh,cu}` | ASTs topológicas indexadas, avaliação em lote e contador de nós efetivamente avaliados |
| `hardware/cuda/{rational_host,host_reference}.cpp` | Referência executável dos mesmos algoritmos, identificada como host |
| `omega_gpu_mcts/tensor_mcts_types.h` | Árvores SoA com capacidade fixa, pais, filhos, visitas, valores e prefixos |
| `omega_gpu_mcts/grammar_masks.cuh` | Máscaras de escopo, conclusão de programas parciais e lowering indexado |
| `omega_gpu_mcts/mcts_kernel.{cuh,cu}` | PUCT racional, redução de warp, expansão concorrente, rollout e backpropagation atômico |
| `omega_gpu_mcts/cuda_api.{h,cu}` | Orçamento de VRAM, streams, eventos, seleção de elite e transferência para memória pinned |
| `omega_gpu_mcts/{build,numeric,flat,backend,cli}.py` | Compilação, ABI Python, referência independente, replay e comandos |
| `omega_abstract_domain/interval_domain.cuh`, `invariant_filter.cu` | Intervalos exatos, exclusão de zero, inclusão de saídas e rejeição conservadora |
| `omega_autotelic/sleep_consolidation.omega` | CSE nativo entre programas aprovados, com estimativa de ganho estrutural |
| `omega_autotelic/abstraction_bank.omega`, `bank.py` | Biblioteca assinada, revalidação e exportação de funções para o frontend genérico |
| `omega_autotelic/{curiosity_engine,curiosity_driver}.py` | Desafios limitados, prioridade por repertório, ociosidade, épocas, sono e supervisão |
| `omega_self_evolve_v2/auto_mutator_v2.omega` | Propostas de identidades a partir de frequências do IR |
| `omega_self_evolve_v2/bridge_lean_filter.py` | Fila assíncrona limitada, prova independente, `.olean` e manifesto Ed25519 |
| `omega_self_evolve_v2/{cycle,cli}.py`, `bootstrap_cycle.sh` | Bootstrap em quatro estágios, adoção, commit restrito e rollback |
| `formal/Tier2/{GPUInvariantBridge,CompilerSelfPreservation}.lean` | Inclusão intervalar, exclusão de zero e preservação condicional de semântica/domínio/gradiente |
| `omega_runtime_verified/proof_envelope.h`, `glass_box_trace.c`, `emitter.py` | Envelope C, buffer circular e instrumentação das ativações reais do backend edge |
| `testes/test_hyper_*.py`, `testes/cuda/rational_stress.cu` | Fluxos numéricos, adversariais, formais, nativos e de GPU |
| `scripts/setup-cuda.sh`, `requirements/cuda-linux-x86_64.lock` | Toolkit opcional com versões e hashes fixos |

`formal/Tier2.lean` agrega a biblioteca, registrada no projeto `formal/tensor`.
CLI, pacotes, distribuição de fontes e monólito incluem os novos componentes.

## Fase 1: aritmética e validação CUDA

```sh
bash scripts/setup-cuda.sh
.venv/bin/python -m pytest -q testes/test_hyper_rational.py
.venv/bin/python -m omega hyper status
```

O toolkit opcional é CUDA 13.4.92 para Linux x86_64, instalado fora da venv.
O script verifica os hashes dos quatro wheels. Ele não instala driver nem cria
uma GPU. É possível compilar os kernels em uma máquina CPU para detectar erros
de CUDA, mas isso não valida sua execução no dispositivo.

`Rational64` tem 16 bytes/alinhamento 16; `Rational128`, 32/32. Os denominadores
são positivos e no máximo `INT64_MAX`; o numerador exclui `INT64_MIN`. Operações
intermediárias usam inteiros de 128 bits e reduzem antes de verificar se o
resultado cabe. Rational128 é representação/intermediário, sem alegação de ALU
128-bit nativa em hardware. Alinhamento não obriga uma instrução `LDG.E.128` ou
uma única transação de 256 bits.

Stein executa 128 rodadas mascaradas no dispositivo para operandos de 64 bits,
256 no auxiliar de 128 bits. A contagem de rodadas independe dos valores; não
há prova sobre as instruções SASS escolhidas pelo compilador. A referência
host pode terminar cedo. A poda usa quocientes de frações contínuas e compara
erros sem produtos que exigiriam 192 bits. O desempate coincide com
`Fraction.limit_denominator`, inclusive para negativos. O erro residual é
retornado como Rational128. Poda não concede invariância de decisão: essa
propriedade exige uma prova de margem separada.

O stress CUDA verifica **10.000.000 de operações**, em blocos de memória
reutilizados, contra referência inteira independente. Sem dispositivo, o alvo
compila e sua execução retorna 77; o teste fica explicitamente ignorado.

## Fases 2 e 3: árvore, avaliação e filtro

```sh
.venv/bin/python -m pytest -q testes/test_hyper_flat.py
.venv/bin/python -m omega hyper benchmark --output artifacts/hyper-benchmark
```

Os arrays de AST são **node-major** `[node,candidate]`, para que threads que
avaliam programas diferentes acessem posições adjacentes. Não existem nós com
ponteiros nem `malloc` no dispositivo. Descritores contêm endereços de buffers
contíguos alocados antecipadamente pelo host. Scratch, literais, raízes,
contagens e dimensões são argumentos explícitos: as assinaturas originalmente
propostas sem essas informações não bastavam para avaliação segura de lotes
arbitrários. Flags da avaliação são por candidato/exemplo, evitando disputa
entre escritas de bytes de exemplos diferentes.

Uma thread percorre um programa topológico; um warp seleciona um ramo MCTS.
O limite atual da busca é de 63 tokens por programa e até um milhão de trials,
sujeito a orçamento de 2 GiB e disponibilidade de VRAM. O avaliador genérico
aceita até 4096 nós por programa. A capacidade de cem mil nós se refere a um
lote, não a cem mil valores simultaneamente em registradores de um warp.

PUCT utiliza valores racionais, priors positivos e raiz inteira do número de
visitas. A raiz inteira é uma escolha heurística, sem prova de optimalidade da
busca. A recompensa é racional em escala fixa `2^20`, arredondada para baixo;
apenas seu numerador é reduzido atomicamente. Seu denominador é imutável.
Limites de trials preservam somas int64 e visitas inteiras exatas em float.
Atualizar numerador e denominador com duas operações atômicas independentes
seria incorreto e não é feito.

O filtro usa intervalos racionais exatos. Denominador cujo intervalo contém
zero, overflow, AST malformada ou saída fora do limite gera máscara zero.
Rejeição pode indicar falta de precisão da análise: `x*x` em `[-2,2]` é
aproximado conservadoramente por `[-4,4]`. Não se interpreta essa rejeição como
prova de que o programa está errado. Os intermediários concretos também são
verificados contra overflow. Não ocorre truncamento numérico silencioso.

A seleção copia para o host no máximo os melhores `ceil(trials/1000)` candidatos,
limitados a 64, junto com contadores. Não há taxa fixa de sobrevivência ou poda:
99,9% é um orçamento de elite, não resultado garantido sobre programas.
O benchmark mede eventos CUDA e verifica a meta de 50 mil nós em um segundo
quando existe GPU. Ausência de hardware é `pending`; meta não atingida é
`failed`. O sistema não promete filtro de dez nanossegundos.

## Fase 4: cartório formal

`LeanBridge` tem pool de no máximo quatro workers e semáforo global de fila.
Os candidatos são ASTs de dados, não C ou Lean fornecidos pelo proponente.
O host valida exemplos e gera obrigações universais de refinamento, incluindo
divisores não nulos. Lean precisa aceitar o teorema e relatar somente os
axiomas permitidos (`propext`, `Classical.choice`, `Quot.sound`).
As caixas de entrada e os limites de saída do Tier‑1 também geram teoremas
independentes de limites no Tier‑2 e são vinculados ao recibo. A prova do
contrato original permanece separada, sem ser enfraquecida pela caixa.

A compilação gera `Candidate.lean`, `Candidate.olean` e `certificate.json`.
`.olean` não possui assinatura intrínseca: Ed25519 assina um manifesto que
vincula o objeto à fonte, especificação, AST e relatório de axiomas. A chave
pública confiável vem do host. O verificador confere assinatura, hashes e
reconstrói a prova; nunca importa um `.olean` arbitrário para executar código.
Máscara, reward e campos `formal_admission` de uma proposta não substituem prova.

Os lemas Tier‑2 formalizam a inclusão/exclusão intervalar e a composição da
equivalência assumida para cada passo. Não são uma prova do código CUDA/SASS,
da cadeia C inteira ou de todo compilador possível. GPU, DMA e código proponente
podem errar sem ganhar autoridade de aprovação por isso.

## Fase 5: sono, biblioteca e evolução

```sh
.venv/bin/python -m omega curiosity --backend host-reference \
  --output artifacts/curiosity --cycles 1
# CUDA é o backend padrão; --forever habilita supervisão contínua explicitamente.
.venv/bin/python -m omega hyper sleep --spec accepted-records.json --output artifacts/curiosity
```

O gerador alterna instâncias afins, polinomiais, controle limitado, equações
diofantinas lineares de constantes e identidades do compilador. É uma família
limitada de problemas formais, sem interpretação automática de intenção humana.
Incerteza de Bernoulli é uma heurística empírica de ordenação, não entropia da
verdade matemática. A busca não prova circuitos mínimos. O supervisor consulta
carga CPU e, no modo CUDA, utilização de GPU; falha de observação não autoriza
um ciclo. O modo host é selecionado explicitamente e identificado nos relatórios.

Épocas aceitas persistem em um histórico limitado. O sono revalida os recibos,
executa CSE entre soluções diferentes e propõe rotinas com ganho estrutural
positivo. Os helpers JSON `.omega` são fontes fixas compiladas pela rota nativa
de bootstrap, com checagens de tags e execução isolada. Sua forma dinâmica não
é aceita pelo passe Python limitado de inferência procedural; ele não é
desabilitado para programas comuns. CSE é um proponente e sua implementação
não recebe uma prova de correção por isso.

Cada abstração precisa de um contrato universal e denominadores válidos antes
de entrar no banco assinado. `AbstractionBank.registry()` disponibiliza as
funções aprovadas ao frontend genérico existente, com expansão e execução
nativas. O vocabulário CUDA permanece a gramática racional limitada; não se
instalam opcodes CUDA arbitrários durante o sono. O banco contém assinaturas e
contratos refinados explícitos, não tipos dependentes universais ou conceitos
semânticos descobertos sem especificação.

```sh
bash omega_self_evolve_v2/bootstrap_cycle.sh \
  --receipt artifacts/proof/certificate.json --public-key authority-public.hex \
  --lhs '(x*2)-x' --output artifacts/generation
# Adoção explícita: acrescentar --install --replace-source --commit.
```

Uma identidade aprovada precisa passar novamente pelo domínio restrito do
matcher de otimização. O bootstrap recompila quatro estágios, compara Cs e
binários e exige um probe que exerça a regra com redução de IR. A instalação
reconstrói o compilador independentemente antes da seleção atômica. Com as
flags indicadas, substitui `omega_selfhost/compiler.omega`, publica fonte e
prova em `omega_selfhost/evolved/<id>/`, e cria um commit local restrito a esses
caminhos. Repositório ou índice com alterações do usuário impede o commit.
Não se faz push automático por época.

A fonte canônica inicial é registrada em estado confiável do host. Gerações
posteriores são reconstruídas a partir dela, substituindo a passagem aprovada;
alterações manuais no compilador não são sobrescritas. Não há síntese irrestrita
de passes, remoção do verificador ou acúmulo arbitrário de patches. Falhas de
reinicialização restauram fonte, seletor e época. `restart_runtime` é um hook
do supervisor; sem daemon, a próxima compilação resolve o novo seletor. O
controle não procura nem encerra processos de terceiros.

## Runtime freestanding

`omega_runtime_verified.emit` instrumenta as ativações do backend edge com
`OmegaTraceRing`, mantido em memória fornecida pelo chamador. Os eventos contêm
sequência, ciclo, nó, operação, ramo e valor racional exato. Saturação sobrescreve
o mais antigo e incrementa `dropped`; overflow dos contadores interrompe a
gravação. O produtor é de uma thread; sincronização de múltiplos produtores é
responsabilidade do host.

`OmegaProofEnvelope` implementa o contrato C solicitado. Seus ponteiros, URI e
hash não verificam sozinhos uma prova nem vinculam automaticamente sensores e
saídas a um certificado. A autenticação/PCI continua no host. O contador de
ciclos é fornecido pelo chamador; não é uma medição de hardware inventada.
Os rastros permitem replay aritmético e auditoria de ramos, não inferência
automática sobre significado médico ou alinhamento de uma IA.

Os resultados observados e pendências de GPU ficam em `validation/hyper-core.md`.
