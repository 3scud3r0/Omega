# Ômega 2.0 — compilador auto-hospedado, execução nativa e núcleo Lean

O compilador de produção está escrito em
[`omega_selfhost/compiler.omega`](omega_selfhost/compiler.omega): lexer, parser,
verificação de formas, lowering da linguagem tensorial, otimizador e emissão de C.
Ele compila a própria fonte. Os estágios 0, 1, 2 e 3 geram C idêntico; os binários
estabilizados também coincidem. Depois do bootstrap, compilar e executar programas
nativos não requer Python.

O backend usa GMP para aritmética racional exata e cobre escalares, vetores,
matrizes, ReLU, gradientes e atualizações. O núcleo independente em Lean verifica
valores observados, todas as coordenadas dos gradientes, autorização das taxas,
sementes, atualizações e a cadeia completa de estados. As otimizações recebem
provas universais de preservação de valores **e gradientes** para cada coordenada.

O Nextorch está incorporado ao pacote como subsistema de propostas neurais. Ômega
faz a admissão exata; os modelos e as interfaces Orange continuam usando
PyTorch/Python. Os compiladores/VMs históricos em Python são preservados como
referência e compatibilidade, não são chamados pelos estágios nativos do compilador.

```sh
# Linux x86_64, Python 3.12, compilador C, libgmp-dev, libssl-dev e zstd.
# Icarus Verilog (iverilog/vvp) habilita os testes de co-simulação RTL.
bash scripts/setup.sh
bash scripts/test.sh -q

.venv/bin/python -m omega bootstrap
.venv/bin/python -m omega native-build exemplos/rede_profunda.omega \
  --saida artifacts/nativo/rede
.venv/bin/python -m omega native-run artifacts/nativo/rede \
  --saida artifacts/nativo/rede-result.json
.venv/bin/python -m omega verify-native artifacts/nativo/rede-result.json

# Otimizador auto-hospedado, com prova universal conferida antes da entrega:
.venv/bin/python -m omega native-build exemplos/otimizacao_ir.omega \
  --saida artifacts/nativo/otimizado --optimize
.venv/bin/python -m omega native-run artifacts/nativo/otimizado
```

Os [16 motores fundamentais](omega_core/README.md) acrescentam pesquisa variacional,
simplex racional, e-graphs, TT, SINDy, aprendizado e microatores com contratos
limitados. Use `.venv/bin/python -m omega_engines list`; exemplos estão em
`exemplos/engines`. A CLI também expõe `omega engines run`, `prove`, `synthesize`
e `arena-native`, com execução isolada e evidências explícitas.

Use destinos novos: os comandos preservam resultados existentes. O executável
`build/selfhost/omegac-stage2` aceita `fonte.omega destino.c` ou
`fonte.omega destino.json --ir`. A entrada `omegac` instalada chama esse compilador.
O bootstrap Python é uma semente auditável do dialeto procedural, não uma
primitiva oculta chamada pelo compilador auto-hospedado.

## Ecossistema nativo e aprovação automática

A biblioteca `std/`, os seis módulos de memória/síntese/agentes e os comandos
`omega native` estão descritos no [mapa de arquivos e contratos](docs/ECOSSISTEMA_NATIVO.md).
A incubadora tem aprovação automática (`--auto-approve`, padrão), sem prompt,
com prova Lean, integridade, benchmark repetido e bootstrap de quatro estágios.
O modo manual continua configurável. `omega native repl` abre o terminal racional.

## Fluxos certificados adicionais

`@omega.certify` exporta grafos PyTorch FX estáticos de operações afins/ReLU
para Ômega/C/GMP com provas Lean de limites e certificados de inferência
assinados. Também estão disponíveis poda racional com margem certificada,
backend racional com escalas fixas freestanding, ações de recursos verificadas, destilação
finita e experimentos de superotimização com recompilação auto-hospedada.
Consulte [APIs, exemplos e domínios das garantias](docs/FLUXOS_CERTIFICADOS.md).

Softmax, RMSNorm e Self-Attention causal/multi-head agora têm aproximações
racionais com limites reais conferidos pelo Lean, binários C/GMP reutilizáveis,
certificados assinados por entrada e famílias de comprimentos limitados.
Veja [Micro-Transformer e benchmark comparativo](docs/TRANSFORMER_CERTIFICADO.md).

O [Caminho C](docs/CAMINHO_C.md) acrescenta tipos refinados, síntese MCTS com
admissão universal em Lean, automutação restrita com quatro estágios de
bootstrap e ações portadoras de prova. Inclui C freestanding com buffers
reutilizados, rastros de inferência, memória linear, escalonamento finito e
uma Q-PU de referência em RTL. O documento lista os arquivos e os limites de
cada garantia.

O [Hyper-Core](docs/HYPER_CORE.md) acrescenta kernels CUDA de aritmética racional,
ASTs planas, MCTS e intervalos, uma ponte assíncrona para objetos Lean assinados,
consolidação nativa de abstrações e evolução com adoção/commit controlados.
Compilação CUDA e execução em GPU são verificações distintas; metas de latência
dependem de medição no dispositivo.

Os três passos e sua base de confiança estão descritos em
[estado dos três passos](docs/ESTADO_DOS_TRES_PASSOS.md).
Veja [linguagem procedural e bootstrap](docs/AUTO_HOSPEDAGEM.md),
[execução nativa e provas](docs/NATIVO_E_LEAN.md) e
[integração Nextorch/Orange](docs/INTEGRACAO_NEXTORCH.md).

## Síntese racional integrada em desenvolvimento para 3.0

```sh
.venv/bin/python -m omega agent synthesize-native exemplos/sintese_racional.json \
  --max-size 3 --max-candidates 100 --saida artifacts/sintese-racional
.venv/bin/python -m omega agent audit-synthesis artifacts/sintese-racional
```

Busca isolada, geração de Ômega, build C/GMP, execução nativa, admissão Lean e
casos reservados ficam unidos em uma entrega auditável. Consulte
[contrato, artefatos e limites](docs/SINTESE_NATIVA_3_0.md).

## Biblioteca científica nativa

Os 115 arquivos solicitados estão catalogados em [ciencia/](ciencia/README.md):
97 módulos Ômega executáveis, 18 arquivos de teoremas Lean e supervisão de
experimentos com contratos delimitados. Consulte os escopos e hipóteses antes
de interpretar uma saída como evidência científica.

```sh
.venv/bin/python -m omega science run 23 exemplos/ciencia/agua.json
.venv/bin/python -m omega science experiment 23 exemplos/ciencia/agua.json \
  --saida artifacts/ciencia-agua
```

## Subsistema neural incorporado

```sh
export OMEGA_LEAN=/workspace/.tools/lean-4.19.0-linux/bin/lean
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
.venv/bin/python -m omega intuition exemplos/tarefas_abertas.json \
  --saida artifacts/intuicao --lean --native
.venv/bin/python -m omega audit-intuition artifacts/intuicao --lean --native
```

No Orange Canvas, abra `exemplos/omega_nextorch.ows` e selecione
`exemplos/intuicao_xor.tab`. O widget **Omega Certifier** só exporta o circuito após
certificação. Os três widgets originais Nextorch continuam disponíveis.

## Documentação do motor 1.3 preservado

**Novo: [síntese aberta e metapolíticas de busca](README_OPEN_1_3.md)**.

# Ômega 1.3.0 — evolução do próprio programa de busca

A Ômega 1.3 (inclui motor 1.2) é um protótipo **realmente executável** de autotransformação **limitada**: ela sintetiza, compila e substitui o **programa Ômega que estabelece a prioridade de busca** de candidatos. Uma auditoria independente reexecuta a busca e prova resultados em um universo *finito* de 16 tarefas booleanas. **Não é uma prova de inteligência artificial geral, consciência, automodificação universal ou progresso ilimitado.**

## Inicialização

Requer Python 3.10 ou superior. Descompacte o ZIP, abra o terminal dentro da pasta `Omega_v1_2` e execute:

```sh
python -m omega --versao
python -m omega meta-evolve minha_metaevolucao
python -m omega audit-meta minha_metaevolucao
python -m omega verify-meta minha_metaevolucao/certificado_meta.json
python -m omega run minha_metaevolucao/politica_ativa.omega
python -m unittest discover -s testes -v
```

O comando `meta-evolve` escreve políticas reais `.omega`, as versões compiladas `.omc`, a política ativa, certificados, resultados e relatório. `audit-meta` recalcula tudo sem confiar na solução alegada pelo gerador. `verify-meta` verifica matematicamente a cadeia sem exigir os arquivos executáveis. O código anterior de XOR e os comandos históricos permanecem disponíveis.

## Autoevolução de código, não apenas da solução

A Ômega começa com uma política de prioridade de busca degenerada (todo candidato tem prioridade 0, e a ordem lexicográfica resolve os empates). A política é um programa `.omega`, compilado pela IR da Ômega, como este exemplo de sucessor:

```omega
parametro a = 0;
parametro b = 0;
parametro c = 0;
parametro d = 0;
tensor prioridade = (1)*(
    (relu(a)+relu(-a)) + (relu(b)+relu(-b)) +
    (relu(c)+relu(-c)) + (relu(d)+relu(-d))
) - a;
mostrar prioridade;
```

O arquivo efetivo é gerado automaticamente em uma única linha de expressão, com parênteses equivalentes. A VM executa a função de prioridade usando quatro valores de uma hipótese candidata. A ordem resultante decide **qual hipótese será testada primeiro**. A seleção do código sucessor depende apenas das oito tarefas de treinamento; outras oito tarefas são reservadas como teste.

O laço de enumeração, a sintaxe, a VM e o verificador independente ainda são implementados em Python. **Não há recompilação de todo o compilador Ômega, auto-hospedagem completa ou modificação do núcleo de confiança.**

## Avaliação reprodutível

A família de funções é `f(x,y)=a+b*x+c*y+d*ReLU(x+y-1)`, com `a,b,c,d` inteiros entre −2 e 2. Existem 625 hipóteses, suficientes para representar as 16 tabelas booleanas de duas entradas. Uma política consiste em cinco pesos inteiros de −1 a 1, que definem uma prioridade de busca. Existem 243 políticas possíveis.

| Evolução do código de busca | Geração 0 | Geração 1 | Geração 2 |
|---|---:|---:|---:|
| Políticas consideradas na etapa | 1 | 11 | 243 |
| Avaliações acumuladas nas oito tarefas de treinamento | 2.902 | 617 | **481** |
| Avaliações acumuladas nas oito tarefas reservadas | 3.106 | 648 | **437** |
| Soma sobre todas as 16 tarefas | 6.008 | 1.265 | **918** |

O desempenho medido é **número de hipóteses examinadas até a primeira solução exata**. Não é tempo de execução, precisão em dados reais, competência geral ou garantia de progresso fora desse universo.

## Base de confiança e limites

O núcleo independente `omega/nucleo_meta.py` verifica completude da família finita, enumeração de todas as 243 políticas, escolha do ótimo na métrica do treinamento e resultados em todas as 16 tabelas. `omega/metaevolucao.py` compila cada política `.omega`, reexecuta a VM sobre **todas as 625 hipóteses** e confere a busca efetiva. Os arquivos gerados são vinculados a seus certificados.

- A prova é **exaustiva e operacional no domínio finito definido**; não é uma prova dentro do kernel Lean 4.
- SHA-256 detecta divergências entre arquivos e o certificado; não fornece autenticação de origem.
- O conjunto de teste é separado do critério de seleção da política, mas pertence à **mesma família de tarefas** e não permite afirmar generalização em domínios novos.
- A política mutável é somente a **função de ordenação**. O algoritmo externo de busca continua fixo, e a segurança de modificações arbitrárias no runtime não foi demonstrada.
- A configuração pequena (625 hipóteses, 243 políticas e 16 problemas) permite prova finita; o resultado **não escala automaticamente** para arquiteturas neurais genéricas.

Consulte `PROVA_META_FINITA.md` para enunciados, derivação algébrica, métricas e limite de validade. Os códigos completos das versões anteriores foram mantidos no TXT de distribuição.

## Ingestão e acompanhamento ao vivo

Os 56 módulos da nova malha, os levantadores estrangeiros e o rastreador com histórico persistente e controles ao vivo estão descritos em [Ingestão e sociedade ao vivo](docs/INGESTAO_E_SOCIEDADE_AO_VIVO.md). Use `omega live --help` e `omega ingest --help`. Os domínios aceitos e as fronteiras das provas são explícitos; operações não suportadas são rejeitadas.
# Kernel nativo amalgamado

`omega_kernel.omega` reúne o verificador dependente embutido, o motor tensorial
racional e os emissores ELF Linux x86-64/AArch64/RISC-V, com fontes C/Python
extraíveis e hashes. Use `omega kernel ...` ou `python -m omega_kernel ...`.
Escopos, limites e dependências estão em [kernel/README.md](kernel/README.md),
e os resultados reais em [kernel/VALIDACAO.md](kernel/VALIDACAO.md).

