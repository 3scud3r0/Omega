# Dezesseis motores de pesquisa executáveis

Os 16 arquivos `.omega` pedidos têm algoritmos nativos, validação de dados,
orçamentos e exemplos executáveis. Não são uma equação universal da física,
uma solução geral de inteligência ou uma certificação de sistemas críticos.
Os 115 módulos científicos anteriores continuam disponíveis.

O [catálogo JSON](catalogo.json) contém exatamente 16 IDs, caminhos, exemplos e
escopos. O auxiliar `algebra.omega`, dois aplicativos, o pacote `omega_engines`,
o microkernel C e o arquivo Lean integram os motores. Os motores rodam em Ômega/C;
o host prepara builds, isola processos e reconstrói contas independentes para
verificar os contratos.

## Uso

```sh
bash scripts/setup.sh
.venv/bin/python -m omega_engines list
.venv/bin/python -m omega engines run 3 exemplos/engines/03-smt_simplex_solver.json
.venv/bin/python -m omega_engines run 6 exemplos/engines/06-universal_action_engine.json
.venv/bin/python -m omega_engines prove 6 exemplos/engines/06-universal_action_engine.json \
  --saida artifacts/engines/action-proof
.venv/bin/python -m omega_engines synthesize \
  exemplos/engines/15-programmatic_hypernetwork_synthesis.json \
  --saida artifacts/engines/synthesized-program
.venv/bin/python -m omega_engines arena-native \
  exemplos/engines/16-cellular_micro_arena_runtime.json \
  --saida artifacts/engines/native-actors
```

Use destinos novos; fontes, resultados e evidências anteriores são preservados.
`build engines_core` e `build engines_ml` mostram os executáveis C/GMP. Cada um
recebe `ID request.json` e emite o codec racional canônico do projeto. O host
converte esse resultado para JSON de apresentação. `omega_engines` não carrega
Torch. O executável científico não inicia Python; seu build e supervisão usam
Python, Linux, libc, GMP, OpenSSL e Bubblewrap.

## Implementações e contratos

| ID / arquivo | Algoritmo entregue | Domínio e limites explícitos |
| --- | --- | --- |
| 1 `taylor_models_interval.omega` | Polinômio univariado + resto intervalar; soma, produto, exp, sin, log e quantização racional com arredondamento para fora | Ordem 1–12, bits 8–128, centro/raio limitados. Log exige `|x-1|<1` em todo o domínio. Truncamento e quantização entram no erro; não é aritmética real exata finita. |
| 2 `egraph_saturation.omega` | Union-find, hash-consing por busca determinística, reconstrução de congruência, regras de anel, extração por custo e checagem polinomial independente | 16–1.024 e-nodes, até 32 rodadas. AST com const/var/add/mul. Não aplica `x/x=1`, não resolve síntese arbitrária nem garante saturação/global ótimo. |
| 3 `smt_simplex_solver.omega` | Simplex racional de duas fases, desempate de Bland, certificados primal/dual, Farkas ou raio de recessão | Maximiza `c*x` com `A*x<=b,x>=0`; até 24 restrições, 12 variáveis e 4.000 pivôs. Não é SMT inteiro/não linear/quantificado. Budget esgotado não vira SAT/UNSAT. |
| 4 `sindy_discovery_engine.omega` | STLSQ exato, seleção de suporte, refit final, ridge opcional, erro retido e emissão de função Ômega | Até 32 amostras, 4 variáveis, 20 monômios e 32 rodadas. Derivadas e medições vêm do usuário. Sistemas singulares falham explicitamente. Ajuste de tabela não prova uma lei empírica. |
| 5 `variational_physics_compiler.omega` | Derivação de Euler–Lagrange em álgebra de jets polinomiais, momentos, Hessiana, energia, identidade de Noether fora da solução e testes de translação/rotação | Até 3 coordenadas, grau de entrada 12 e 512 termos intermediários. Variáveis `[q...,v...,t]`, acelerações anexadas. Não gera Einstein/Dirac/Navier–Stokes gerais. |
| 6 `universal_action_engine.omega` | `derive` chama o compilador variacional; `simulate` usa Verlet variacional e checa DEL/Jacobiano; `dec` constrói fronteiras e cobordos de complexo simplicial finito | Sistemas separáveis de potencial polinomial, massa positiva, 1–3 coordenadas, até 256 passos; complexos de até 8 vértices, 16 facetas e dimensão 3. Energia física e drift são reportados, não presumidos constantes. |
| 7 `renormalization_multiscale_engine.omega` | Complemento de Schur, reconstrução dos graus rápidos e igualdade de energia quadrática; médias por blocos com decomposição exata da variância | Hessiana SPD 2–12, variáveis lentas primeiro. Eliminação condicional quadrática; normalização da integral gaussiana excluída. Não deduz equações macroscópicas gerais a partir de quarks. |
| 8 `tensor_network_compressor.omega` | TT por colunas-pivô e projeções racionais, resíduo de reconstrução Frobenius calculado integralmente; contração e norma por transferências | Compressão densa até 1.024 entradas, ordem 8; contração de TT fornecido até ordem 64, dimensão/posto 8 e 10.000 escalares. Não implementa SVD ótima/DMRG nem comprime todo estado emaranhado em posto pequeno. |
| 9 `active_inference_grounding.omega` | Bayes finito exato, previsão POMDP e planejamento por risco KL + ambiguidade com logs intervalares | Até 8 estados/observações, 4 ações, horizonte 3 e 256 nós. Proveniência/sequence registradas, origem não autenticada. A máscara limita propostas; nenhum sensor ou atuador é acionado. |
| 10 `universal_constructor_autopoiesis.omega` | Rede de Petri catalítica com conservação, capacidades e histórico; proposta de reparo por blueprint cujo hash coincide com a âncora declarada | 16 espécies, 32 regras e 512 eventos. Primeira quantidade conservada tem pesos positivos. Reparos não são aplicados, código não se replica, âncora não é autenticada automaticamente. |
| 11 `../omega_ml/equilibrium_propagation_engine.omega` | Relaxações livre/nudged de energia quadrática, derivada contrastiva local e cotas do erro de relaxação | Até 16 neurônios, pesos simétricos, dominância diagonal estrita, até 512 iterações. O viés de beta finito é separado do erro de relaxação. Memória O(n²) de pesos + O(n) de estados, sem histórico temporal; não O(1) global. |
| 12 `../omega_ml/continuous_hopfield_ssm.omega` | Recorrência linear de estados + banco FIFO de chaves/valores e recuperação softmax intervalar | Banco de até 32 itens, estado/chaves até dimensão 16; norma recorrente <=1, até 32 iterações. Colisões, mistura e evicção existem. Não há contexto infinito ou recuperação perfeita garantida. |
| 13 `../omega_ml/causal_do_calculus.omega` | Enumeração de SCM binário, observação, `do`, abdução/contrafactual com mesmo mundo exógeno e ajuste backdoor com separação em grafo ancestral moralizado | Até 12 nós, 8 variáveis exógenas e 256 mundos. DAG fornecido em ordem topológica. Backdoor verifica raízes independentes, controles sem descendentes e positividade. Não descobre o grafo real nem implementa identificação causal geral. |
| 14 `../omega_ml/jepa_latent_world_model.omega` | Encoder/preditor lineares treináveis, alvo EMA com stop-gradient e penalidades de variância/covariância com gradientes explícitos | Batch 2–32, entrada 16, latente 8 e até 32 épocas sob budget de bits. A penalidade usa variância, não desvio padrão. Colapso é diagnosticado, não matematicamente excluído. Sem alegação de eficiência 1.000× ou bom senso geral. |
| 15 `../omega_ml/programmatic_hypernetwork_synthesis.omega` | Hiper-rede linear treinável que gera coeficientes de DSL polinomial e programa Ômega; casos verificáveis e caminho de compilação real | Até 16 features/monômios, 4 variáveis, grau 12, 32 casos. Bias deve ser feature explícita. A CLI compila e executa o candidato isolado, compara referência racional e verifica fatos numéricos no Lean. Não prova generalização OOD. |
| 16 `cellular_micro_arena_runtime.omega` | Escalonador round-robin cooperativo, registradores, filas circulares, backpressure, yield, saltos, asserts, detecção de quiescência/deadlock e cotas | Até 256 atores, 16 registradores, 64 mensagens/fila, 128 instruções, quantum 64 e 100.000 turnos. Protocolo fechado, sem callbacks arbitrários. Modelo Ômega usa o runtime GMP normal; backend C tem buffers realmente fixos. |

Todos os escalares científicos usam racionais ou strings racionais. Floats,
bools e null são recusados na entrada. O supervisor limita bytes, nós,
profundidade, CPU, RAM, tempo e saídas. Há ainda um limite intermediário de 8.192
bits; configurações estruturalmente válidas podem exceder o orçamento de bits ou
combustível. Falhar por orçamento não equivale a refutar uma hipótese.

## Microkernel C e memória

`runtime/cellular_micro_arena.h` é um núcleo sem alocação dinâmica, I/O, OS ou
threads. Recebe armazenamento contíguo e bytecode imutável do chamador. Compila
como freestanding com suporte do compilador a `__int128`; helpers aritméticos
da toolchain ainda podem ser necessários. Não foi validado em Cortex/RISC-V.
O harness Linux usa mmap/stdio e executa sob sandbox; ele não é firmware.

O wheel inclui os fontes para catálogo/build/run e para o backend de arenas.
Os comandos com Lean (`prove` e `synthesize`) requerem o checkout e o projeto
formal preparados; não baixam uma toolchain ou dependências por conta própria.

Cada arena tem 4.096–524.288 bytes e alinhamento de oito bytes. A cota lógica é
`atores*arena_bytes + instrucoes*64 + 256`, verificada antes de executar. O C
também verifica alinhamento, tamanho real de seus descritores, registradores,
opcodes, filas e limites dos saltos. Os racionais do backend usam magnitude de
numerador e denominador até `INT64_MAX`, com intermediários de 128 bits,
redução exata e erro explícito quando o resultado não cabe. A API recusa runtimes
nulos/não inicializados e IDs de ator fora da faixa. O GMP de outros
motores não é silenciosamente convertido para esse formato.

O teste diferencial compara registradores, PCs, estados, filas, contadores e
deadlock entre Ômega e C. O receipt registra bytes de arena alocados e tamanho
do controle C. Não mede nem promete RSS total por ator, inteligência em 512 KB,
troca de contexto em nanossegundos, M:N, lock-free, AVX/GPU batching ou milhares
de processos Lean dentro dessas arenas. São atores stackless, não fibras C com
pilha própria. O custo dos modelos, sistema operacional e verificador é separado.

## Provas automáticas e confiança

`formal/HamiltonPrinciple.lean` prova seis enunciados discretos: variação exata
da ação quadrática local, recorrência estacionária, variação quando DEL=0,
determinante do Jacobiano kick–drift–kick, `d²=0` no triângulo e balanço algébrico
de trabalho/energia. O build `EngineAxioms` os verifica e audita suas dependências.
Não se adicionam axiomas físicos, `sorry` ou `admit`.

`engines prove` aceita apenas contratos revisados para IDs 3, 6 e 7:
certificados LP; passos, condições iniciais, DEL e identidade simplética em uma
trajetória finita; equivalência quadrática em probe explícito ou variância por
blocos. Reconstrói a conta fora do proponente e envia até 256 obrigações fechadas,
em batches de 32, ao Lean. Para o LP, um template adicional prova um enunciado
quantificado: limite objetivo para toda atribuição racional viável, inexistência
de atribuição viável ou uma família de pontos viáveis ao longo de raio com
crescimento objetivo estritamente positivo. O enunciado contém os coeficientes
do problema recebido; não é apenas uma igualdade de valores calculados.
Uma obrigação falsa ou observação adulterada bloqueia
o receipt. Outros IDs recusam esse comando; não escolhem um verificador mais fraco.

`engines synthesize` compila o programa do ID 15, executa cada caso em sandbox,
compara saída com avaliação racional independente e os valores esperados, e
verifica igualdades coeficiente/monômio/resultado no Lean. Entrega fonte Ômega,
C, ELF, headers, logs, `.olean`, hashes e receipts. Isso certifica os fatos
numéricos declarados nos casos, não o compilador geral nem todas as entradas.
O statement de cada certificado continua disponível para revisão.

O host usa snapshots dos pedidos e hashes dos fontes/artefatos. Cache adulterado
é rejeitado. SHA-256 não autentica sozinho um sensor, autor, origem de software
ou instante de descoberta. Não há publicação, controle de laboratório, despacho
de atuadores, modificação própria ou promoção automática nesta interface.

## Correções científicas ao texto proposto

- Ação estacionária não significa sempre mínimo; uma Lagrangiana simples não
  cobre automaticamente dissipação, física de muitos corpos ou toda a biologia.
- Preservação simplética e aritmética racional não eliminam erro de modelo,
  discretização ou instabilidades físicas. Não há garantia de órbita segura por
  décadas nem de funcionamento de um dispositivo médico apenas por compilar.
- `d²=0` explica uma identidade de Bianchi/divergência magnética; não é por si só
  um teorema de conservação de carga elétrica de todo modelo.
- Renormalização e TT exploram estrutura. Sem hipóteses de escala/posto, custos
  exponenciais e perda de informação permanecem.
- Inferência ativa, EqProp, JEPA e hiper-redes não garantem descobertas, contexto
  infinito ou generalização universal. Essas alegações exigem experimentos.
- Os módulos anteriores têm algoritmos e provas de escopo delimitado. Não se
  presume que sejam esqueletos ou provas admitidas: seu relatório registra as
  execuções e a auditoria efetivamente realizadas.

## Verificação

```sh
(cd formal/tensor && lake build EngineAxioms)
.venv/bin/python -m pytest testes/engines -q
bash scripts/test.sh -q --junitxml=artifacts/engines/full.xml
```

Há oráculos de precisão decimal, enumeração exata de vértices LP, contrafactuais,
diferenças finitas de gradientes, testes adversariais, builds instalados sem Torch,
execução real de programas gerados, comparação de schedulers e ASan/UBSan do C.
Testes aprovados não substituem revisão independente ou validação empírica.
