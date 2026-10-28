# Caminho C: implementação e fronteiras

Este incremento conecta especificações racionais, síntese por MCTS, obrigações
Lean, mutações restritas do compilador e ações externas autorizadas. Os
componentes de inferência racional, poda, PCI, Softmax, RMSNorm e self-attention
dos incrementos anteriores continuam integrados. Não há substituição universal
do PyTorch, solução da equivalência de programas arbitrários ou garantia sobre
propriedades que não foram escritas no contrato.

## Manifesto dos arquivos

| Arquivos | Responsabilidade |
| --- | --- |
| `omega_refine_check/syntax.py` | Gramática limitada, AST sem `eval`, aliases e anotações |
| `omega_refine_check/contracts.py`, `lean.py` | Obrigações universais, denominadores e predicados vetoriais |
| `omega_refine_check/compiler.py`, `cli.py` | Parser nativo independente, prova antes de compilar, auditoria |
| `omega_selfhost/compiler.omega`, `bootstrap.py`, `driver.py` | Extração nativa de refinamentos e integração com bootstrap |
| `omega_synth_mcts/grammar.py`, `policy.py` | ASTs parciais, PUCT, guia heurístico ou pequena rede opcional |
| `omega_synth_mcts/search.py`, `pruning.py`, `worker.py`, `cli.py` | Busca limitada, poda justificada, processo isolado e admissão universal |
| `omega_self_mutate/rules.py`, `profiler.py` | Descoberta de identidades, perfil do IR e tempos observados do binário |
| `omega_self_mutate/bootstrap.py`, `activation.py`, `cli.py` | Quatro estágios nativos, ponto fixo, reconstrução independente e seleção atômica |
| `omega_agent_sandbox/actions.py`, `policy.py`, `proofs.py` | Transições simultâneas, contrato de Hoare e vínculo criptográfico |
| `omega_agent_sandbox/ledger.py`, `runtime.py`, `adapters.py`, `cli.py` | Reserva durável, CAS, capabilities e efeitos registrados pelo host |
| `omega_cognition/linear.py`, `memory.py` | Posse exclusiva, empréstimos e reutilização por última utilização |
| `omega_cognition/scheduler.py` | Prioridade aprendida dentro de uma política de progresso finito |
| `omega_cognition/glass.py`, `omega/real_native.py` | Eixos ortonormais, conceitos com contratos e rastros nativos verificáveis |
| `omega_cognition/standalone.py`, `pipeline.py`, `qpu.py`, `cli.py` | Exportação C, destilação de especificações e referência racional de hardware |
| `omega_selfhost/bounded_rational.h`, `proof_microkernel.h` | Aritmética limitada sem heap e arena com handles geracionais |
| `hardware/qpu/{gcd_stein,stern_brocot,rational_alu}.sv` | Circuitos de referência simuláveis |
| `formal/tensor/Omega/{Refinement,MCTSPruning,VerifiedRewrite,LinearMemory,Lyapunov,Glass}.lean` | Lemas dos novos domínios |
| `formal/tensor/Main.lean` | Reificação de equivalência de valor, gradiente e domínio de definição |
| `testes/test_{refinement,mcts_synthesis,self_mutate,proof_actions,cognition,qpu_rtl,path_c_integration}.py` | Fluxos nativos, provas e rejeições adversariais |
| `omega/cli.py`, `pyproject.toml`, `MANIFEST.in`, `scripts/build-monolith.py` | Comandos, distribuição e artefato monolítico reproduzível |

Todos os novos pacotes têm `__init__.py`. Exemplos executáveis ficam em
`exemplos/path_c/`. O relatório de validação fica em `validation/path-c.md`.

## Tipos refinados e síntese

```sh
.venv/bin/python -m omega refine check exemplos/path_c/probability.omega
.venv/bin/python -m omega refine build exemplos/path_c/probability.omega --output artifacts/probability
.venv/bin/python -m omega synth exemplos/path_c/increment.json --output artifacts/increment --iterations 256
```

`Rational` e `Tensor[Rational,N]` aceitam predicados `where { ... }`, aliases,
índices constantes, `self.denom`, norma euclidiana limitada, soma e produto
interno. O domínio atual de programas refinados é de declarações puras com
formas estáticas. Matrizes gerais, funções recursivas, laços e efeitos não são
aceitos por este frontend. Cada inicializador é verificado antes de assumir o
contrato do novo parâmetro: um tipo impossível não permite aprovar seu próprio
inicializador por vacuidade. Divisões precisam de prova de divisor não nulo.

O MCTS expande ASTs com buracos e usa exemplos apenas como fitness. A admissão
é uma proposição universal sobre entradas racionais sob premissas explícitas.
Ela não prova que as premissas descrevem o mundo nem que são satisfatíveis.
Falha de prova ou esgotamento do orçamento retorna rejeição. A poda Lean atual
detecta divisores literalmente nulos em subárvores; não é um resolvedor geral
de invariantes parciais. `isolated_search` executa o proponente sem rede, com
limites do sistema, e verifica a proposta novamente no host. `search` permite
guias locais confiáveis, incluindo `NeuralPolicy`, sem lhes dar autoridade de
aprovação. A busca não prova minimalidade nem encontra todo programa existente.

## Automutação verificável

```sh
.venv/bin/python -m omega mutate discover --lhs '(x*2)-x'
.venv/bin/python -m omega mutate profile --source exemplos/path_c/probability.omega
.venv/bin/python -m omega mutate evolve --lhs '(x*2)-x' --output artifacts/generation
.venv/bin/python -m omega mutate activate --output artifacts/generation
.venv/bin/python -m omega mutate deactivate
```

O MCTS propõe uma identidade polinomial escalar que elimina a expressão para
uma variável capturada. Um matcher controlado é incorporado a uma cópia de
`compiler.omega`. Não se aceita patch arbitrário, alteração do verificador ou
remoção da autorização. O pipeline recompila quatro gerações e exige igualdade
dos C gerados e estabilização dos binários. Um programa derivado da regra deve
exercitá-la e reduzir o número de nós de IR.

Cada mapa concreto de otimização gera provas de igualdade para todos os
ambientes: valor, gradiente e domínio de definição. O certificado JSON v2 só
solicita a geração das provas; o verificador de dados não o considera válido
sozinho. O resultado só é admitido depois da verificação Lean. Os teoremas
abstratos de composição são condicionais à preservação de cada geração; não
constituem uma prova completa do compilador C ou de sua cadeia de ferramentas.

Antes da ativação, a auditoria reconstrói a fonte pelo template confiável e
recompila independentemente, comparando todos os estágios. Um manifesto com
hashes forjados de um binário alterado é recusado. A seleção padrão usa
`build/selfhost/active.json`; mudanças na base confiável invalidam a seleção.
Desativar restaura o compilador canônico sem apagar a geração. A métrica atual
é tamanho de IR no probe, não aceleração universal nem garantia de ausência de
bugs em toda entrada de qualquer compilador futuro.

## Ações portadoras de prova

```sh
.venv/bin/python -m omega action exemplos/path_c/cooling-policy.json \
  exemplos/path_c/cooling-state.json exemplos/path_c/cooling-action.json \
  --output artifacts/cooling
```

A CLI prepara artefatos com uma chave efêmera explícita; não despacha efeitos.
O host configura `Runtime` com política imutável, chave pública, verificador
de capabilities assinadas, ledger SQLite e adaptadores permitidos. O bundle
vincula política, versão de estado, parâmetros, código, prova e nonce. O host
reconstrói a ação a partir da política e não executa Lean ou código livre
fornecido pelo agente. Após prova e execução nativa da transição pura, revalida
a autorização e reserva o estado por CAS antes de chamar o adaptador.

Assinatura válida não concede permissão: a capability precisa autorizar o hash
da ação exata. Replay e estado obsoleto são rejeitados. Um efeito externo e uma
transação SQLite não são atomicamente acopláveis em geral: se houver falha ou
perda de confirmação, o domínio permanece bloqueado para reconciliação pelo
host. Não há retry automático de efeito incerto. A prova diz respeito ao modelo
de transição; sensores, motor, API, host e correspondência com o mundo físico
continuam sendo hipóteses. Os testes usam apenas adaptadores locais gravadores.

## C independente, memória e progresso

```sh
.venv/bin/python -m omega compile weights.pt --standalone \
  --contracts architecture-and-bounds.json --target omega_model.c
```

O manifesto contém `architecture` (camadas `linear` com `in`, `out`, `bias`, e
`relu`), `input_bounds`, `output_bounds` e `input_scale`. O checkpoint deve ser
um `state_dict` carregável com `weights_only=True`; módulos pickle arbitrários
não são executados. O resultado usa buffers fixos reutilizados após a última
leitura, escalas racionais exatas e verificações de overflow estáticas. O
backend freestanding é afim/ReLU em uma grade int64 declarada. GMP tem alocação
dinâmica e não recebe a alegação de zero heap. Transformers continuam no backend
GMP com intervalos certificados das funções reais, conforme o incremento anterior.

O núcleo C oferece handles de arena com gerações, posse e empréstimos. É uma
biblioteca freestanding, não um sistema operacional com isolamento de processos
ou drivers. O escalonador admite prioridade aprendida com sobreposição de
justiça e potencial natural estritamente decrescente para uma carga finita,
sem novas chegadas na época analisada. Ele não prova estabilidade de um SO
arbitrário com entradas e falhas externas.

## Representações e hardware

Bases racionais precisam ser exatamente ortonormais. Um conceito recebe prova
apenas por um predicado lógico explícito sobre sua projeção; o nome de um eixo
não prova monossemanticidade de linguagem natural. Rastros registram operações,
valores, pais, ramos ReLU e intervalos. O runtime nativo pode exportar todos os
intermediários, comparados com execução racional independente e acompanhados
por provas de limites dos nós selecionados. Replay verifica o vínculo com o
grafo, entradas e decisões. Isso não equivale a interpretar automaticamente um
LLM ou converter atenção em uma explicação causal médica.

A Q-PU tem referência Python, lemas racionais por operação e RTL simulável.
Consulte `hardware/qpu/README.md` para interface, interrupções e limites. Não
há chip físico, prova formal RTL, temporização garantida ou velocidade em
nanossegundos. Hipóteses em linguagem natural entram em `distill` com uma
especificação formal fornecida; o sistema não converte intenção ambígua em
axiomas verdadeiros automaticamente.
