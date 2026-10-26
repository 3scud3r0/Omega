# Inventário proposto de arquivos para OM-001 a OM-150
Este mapa preserva as ações do planejamento original. Fontes de implementação e testes foram preenchidos; os planos de validação foram acrescentados, sem execução. “Criar” e “alterar/revalidar” mantêm a intenção histórica e não registram aceite.
OM-001 a OM-017 têm implementação anterior e revisão/revalidação pendentes. A OM-018 foi refeita e aguarda validação. OM-019 a OM-150 têm fontes e checks escritos, com execução pendente. Presença de arquivos não demonstra os critérios de aceite.
Os testes abaixo têm fontes entregues, ainda sem execução nesta revisão. Os descritores novos de evidência estão marcados `not_run`, com resultados nulos; não representam aprovação. O índice e as instruções estão em `validation/README.md`.
## Arquivos compartilhados
- `omega/cli.py` — alterar/revalidar.
- `omega_selfhost/cli.py` — alterar/revalidar.
- `omega_selfhost/driver.py` — alterar/revalidar.
- `omega_platform/manifest.py` — alterar/revalidar.
- `formal/tensor/Main.lean` — alterar/revalidar.
- `formal/tensor/lakefile.lean` — alterar/revalidar.
- `.github/workflows/tests.yml` — alterar/revalidar.
- `scripts/setup.sh` — alterar/revalidar.
- `scripts/test.sh` — alterar/revalidar.
- `pyproject.toml` — alterar/revalidar.
- `MANIFEST.in` — alterar/revalidar.
- `requirements/cpu-py312.lock` — alterar/revalidar.
- `roadmap/progress.json` — alterar/revalidar.
- `roadmap/tasks.tsv` — alterar/revalidar.
- `scripts/build-monolith.py` — alterar/revalidar.
- `scripts/monolith-components.py.txt` — alterar/revalidar.
- `omega/omega_3_monolith.py` — alterar/revalidar.
- `MANIFESTO_SHA256.txt` — alterar/revalidar.
- `omega_agent/__init__.py` — criar.
- `omega_bench/__init__.py` — criar.
- `omega_coder/__init__.py` — criar.
- `omega_evolution/__init__.py` — criar.
- `omega_learning/__init__.py` — criar.
- `omega_memory/__init__.py` — criar.
- `omega_security/__init__.py` — criar.
- `omega_tools/__init__.py` — criar.

## Fase 0

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-001 | Corrigir instalação e compilação da Mathlib | `omega_selfhost/ProofPrelude.lean` (alterar/revalidar)<br>`omega_selfhost/proof.py` (alterar/revalidar)<br>`formal/tensor/lakefile.lean` (alterar/revalidar)<br>`scripts/setup-native.sh` (alterar/revalidar) | `testes/foundation/test_proof_build.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |
| OM-002 | Corrigir e parametrizar a contagem de exemplos válidos | `omega_platform/corpus.py` (alterar/revalidar)<br>`scripts/regression.py` (alterar/revalidar)<br>`testes/corpus.json` (alterar/revalidar) | `testes/foundation/test_corpus.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |
| OM-003 | CI com matriz Linux, versões fixadas e ambientes limpos | `.github/workflows/tests.yml` (alterar/revalidar)<br>`scripts/setup.sh` (alterar/revalidar)<br>`requirements/cpu-py312.lock` (alterar/revalidar) | `testes/foundation/test_proof_build.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |
| OM-004 | Testes de regressão para todos os programas .omega | `omega_platform/corpus.py` (alterar/revalidar)<br>`testes/corpus.json` (alterar/revalidar) | `testes/foundation/test_corpus.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |
| OM-005 | Fuzzing de lexer, parser, IR, JSON e runtime | `omega_platform/security.py` (alterar/revalidar)<br>`scripts/security.py` (alterar/revalidar)<br>`testes/foundation/runtime_harness.c` (alterar/revalidar) | `testes/foundation/test_sandbox.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |
| OM-006 | Sanitizers e análise estática de C | `omega_platform/security.py` (alterar/revalidar)<br>`.github/workflows/tests.yml` (alterar/revalidar) | `testes/foundation/test_sandbox.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |
| OM-007 | Orçamentos de tempo, memória, CPU, profundidade e combustível | `omega_platform/budget.py` (alterar/revalidar)<br>`omega_platform/sandbox.py` (alterar/revalidar)<br>`omega_selfhost/runtime.h` (alterar/revalidar) | `testes/foundation/test_sandbox.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |
| OM-008 | Sandbox para executar programas não confiáveis | `omega_platform/sandbox.py` (alterar/revalidar)<br>`omega_platform/_supervisor.py` (alterar/revalidar)<br>`scripts/setup-sandbox.sh` (alterar/revalidar) | `testes/foundation/test_sandbox.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |
| OM-009 | Manifesto de builds e hashes dos artefatos | `omega_platform/manifest.py` (alterar/revalidar)<br>`scripts/build-manifest.py` (alterar/revalidar)<br>`scripts/package.py` (alterar/revalidar) | `testes/foundation/test_manifest.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |
| OM-010 | Documentação de invariantes e modelo de ameaças | `docs/FUNDACAO_3_0.md` (alterar/revalidar) | `testes/foundation/test_sandbox.py` (alterar/revalidar) | `roadmap/evidence/phase0-corpus.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-security.json` (alterar/revalidar)<br>`roadmap/evidence/phase0-tests.json` (alterar/revalidar) |

## Fase 1

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-011 | Especificação formal de sintaxe e semântica Ômega | `omega_selfhost/OperationalSemantics.lean` (alterar/revalidar)<br>`docs/SINTAXE_E_SEMANTICA.md` (alterar/revalidar) | `testes/foundation/test_operational_semantics.py` (alterar/revalidar) | `roadmap/evidence/om011.json` (alterar/revalidar) |
| OM-012 | Sistema de tipos estático com inferência | `omega/typesystem.py` (alterar/revalidar)<br>`omega/procedural_types.py` (alterar/revalidar)<br>`omega_selfhost/driver.py` (alterar/revalidar) | `testes/foundation/test_type_inference.py` (alterar/revalidar) | `roadmap/evidence/om012.json` (alterar/revalidar) |
| OM-013 | Tipos de tensores com dimensões verificáveis | `omega/dimensions.py` (alterar/revalidar)<br>`omega/typesystem.py` (alterar/revalidar) | `testes/foundation/test_dimensions.py` (alterar/revalidar) | `roadmap/evidence/om013.json` (alterar/revalidar) |
| OM-014 | IR canônica, tipada e versionada | `omega/typed_ir.py` (alterar/revalidar)<br>`omega/nucleo_v1.py` (alterar/revalidar) | `testes/foundation/test_typed_ir.py` (alterar/revalidar) | `roadmap/evidence/om014.json` (alterar/revalidar) |
| OM-015 | SSA e grafo de dependências | `omega/ssa.py` (alterar/revalidar) | `testes/foundation/test_ssa.py` (alterar/revalidar) | `roadmap/evidence/om015.json` (alterar/revalidar) |
| OM-016 | Tratamento explícito de erros e resultados | `omega_platform/results.py` (alterar/revalidar)<br>`omega_platform/sandbox.py` (alterar/revalidar)<br>`omega_selfhost/runtime.h` (alterar/revalidar) | `testes/foundation/test_results.py` (alterar/revalidar) | `roadmap/evidence/om016.json` (alterar/revalidar) |
| OM-017 | Módulos, importações e resolução de nomes | `omega/modules.py` (alterar/revalidar)<br>`omega_selfhost/driver.py` (alterar/revalidar) | `testes/foundation/test_modules.py` (alterar/revalidar) | `roadmap/evidence/om017.json` (alterar/revalidar) |
| OM-018 | Funções genéricas e abstrações reutilizáveis | `omega/generics.py` (alterar/revalidar)<br>`omega_selfhost/driver.py` (alterar/revalidar)<br>`omega_selfhost/cli.py` (alterar/revalidar) | `testes/foundation/test_generics.py` (preservado)<br>`testes/acceptance/test_om018.py` (criar) | `roadmap/evidence/om018.json` (alterar/revalidar) |
| OM-019 | Biblioteca padrão de estruturas de dados | `omega_selfhost/stdlib.omega` (criar)<br>`omega/stdlib.py` (criar) | `testes/acceptance/test_om019.py` (criar) | `roadmap/evidence/om019.json` (criar) |
| OM-020 | Gerenciamento de memória nativa | `omega_selfhost/memory.h` (criar)<br>`omega_selfhost/runtime.h` (alterar/revalidar)<br>`omega_selfhost/tensor_runtime.h` (alterar/revalidar) | `testes/acceptance/test_om020.py` (criar) | `roadmap/evidence/om020.json` (criar) |
| OM-021 | Execução concorrente determinística quando exigida | `omega_platform/scheduler.py` (criar)<br>`omega_platform/sandbox.py` (alterar/revalidar) | `testes/acceptance/test_om021.py` (criar) | `roadmap/evidence/om021.json` (criar) |
| OM-022 | Backend WebAssembly isolável | `omega_selfhost/wasm_backend.py` (criar)<br>`omega_selfhost/runtime_wasm.c` (criar)<br>`omega_platform/wasm.py` (criar) | `testes/acceptance/test_om022.py` (criar) | `roadmap/evidence/om022.json` (criar) |
| OM-023 | Backend LLVM ou compilação nativa otimizada | `omega_selfhost/native_backend.py` (criar)<br>`omega_selfhost/driver.py` (alterar/revalidar) | `testes/acceptance/test_om023.py` (criar) | `roadmap/evidence/om023.json` (criar) |
| OM-024 | Depurador, profiler e rastreamento de IR | `omega/debugger.py` (criar)<br>`omega/profiler.py` (criar)<br>`omega/trace.py` (criar)<br>`omega/motor_v1.py` (alterar/revalidar) | `testes/acceptance/test_om024.py` (criar) | `roadmap/evidence/om024.json` (criar) |
| OM-025 | Sistema de pacotes com dependências verificadas | `omega/packages.py` (criar)<br>`omega/package_lock.py` (criar)<br>`omega/modules.py` (alterar/revalidar) | `testes/acceptance/test_om025.py` (criar) | `roadmap/evidence/om025.json` (criar) |

## Fase 2

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-026 | Semântica denotacional e operacional do núcleo tensorial | `formal/tensor/Omega/TensorDenotation.lean` (criar)<br>`formal/tensor/Omega/TensorOperational.lean` (criar) | `testes/acceptance/test_om026.py` (criar)<br>`testes/lean/OM026.lean` (criar) | `roadmap/evidence/om026.json` (criar) |
| OM-027 | Prova de preservação de tipos | `formal/tensor/Omega/Types.lean` (criar)<br>`formal/tensor/Omega/Preservation.lean` (criar) | `testes/acceptance/test_om027.py` (criar)<br>`testes/lean/OM027.lean` (criar) | `roadmap/evidence/om027.json` (criar) |
| OM-028 | Prova de progresso ou erros tipados | `formal/tensor/Omega/Progress.lean` (criar) | `testes/acceptance/test_om028.py` (criar)<br>`testes/lean/OM028.lean` (criar) | `roadmap/evidence/om028.json` (criar) |
| OM-029 | Provas de correção das transformações de IR | `formal/tensor/Omega/IRTransformations.lean` (criar)<br>`omega/otimizador_v1.py` (alterar/revalidar) | `testes/acceptance/test_om029.py` (criar)<br>`testes/lean/OM029.lean` (criar) | `roadmap/evidence/om029.json` (criar) |
| OM-030 | Verificador de equivalência entre IR original e otimizada | `omega/equivalence.py` (criar)<br>`omega_selfhost/driver.py` (alterar/revalidar) | `testes/acceptance/test_om030.py` (criar)<br>`testes/lean/OM030.lean` (criar) | `roadmap/evidence/om030.json` (criar) |
| OM-031 | Refinamento da máquina abstrata para o backend C | `formal/tensor/Omega/CModel.lean` (criar)<br>`formal/tensor/Omega/CRefinement.lean` (criar) | `testes/acceptance/test_om031.py` (criar)<br>`testes/lean/OM031.lean` (criar) | `roadmap/evidence/om031.json` (criar) |
| OM-032 | Contratos formais para primitivas GMP e tensor runtime | `formal/tensor/Omega/GMPContracts.lean` (criar)<br>`formal/tensor/Omega/RuntimeContracts.lean` (criar) | `testes/acceptance/test_om032.py` (criar)<br>`testes/lean/OM032.lean` (criar) | `roadmap/evidence/om032.json` (criar) |
| OM-033 | Provas de derivação automática e regra da cadeia | `formal/tensor/Omega/AutodiffCorrectness.lean` (criar)<br>`omega_selfhost/TensorKernel.lean` (alterar/revalidar) | `testes/acceptance/test_om033.py` (criar)<br>`testes/lean/OM033.lean` (criar) | `roadmap/evidence/om033.json` (criar) |
| OM-034 | Semântica explícita de subgradientes e ReLU | `formal/tensor/Omega/Subgradients.lean` (criar)<br>`omega_selfhost/TensorKernel.lean` (alterar/revalidar) | `testes/acceptance/test_om034.py` (criar)<br>`testes/lean/OM034.lean` (criar) | `roadmap/evidence/om034.json` (criar) |
| OM-035 | Provas matriciais abstratas sem escalarização integral | `formal/tensor/Omega/MatrixProofs.lean` (criar) | `testes/acceptance/test_om035.py` (criar)<br>`testes/lean/OM035.lean` (criar) | `roadmap/evidence/om035.json` (criar) |
| OM-036 | Certificados compactos e checagem incremental | `omega_platform/proof_cache.py` (criar) | `testes/acceptance/test_om036.py` (criar) | `roadmap/evidence/om036.json` (criar) |
| OM-037 | Correspondência entre enunciado e certificado | `omega_selfhost/statement_binding.py` (criar)<br>`omega_selfhost/proof.py` (alterar/revalidar) | `testes/acceptance/test_om037.py` (criar) | `roadmap/evidence/om037.json` (criar) |
| OM-038 | Verificação de hipóteses, axiomas e dependências Lean | `omega_selfhost/axiom_policy.py` (criar)<br>`omega_selfhost/proof.py` (alterar/revalidar) | `testes/acceptance/test_om038.py` (criar) | `roadmap/evidence/om038.json` (criar) |
| OM-039 | Protocolo de prova com formato canônico | `omega_selfhost/proof_protocol.py` (criar)<br>`omega_security/encoding.py` (integrar) | `testes/acceptance/test_om039.py` (criar) | `roadmap/evidence/om039.json` (criar) |
| OM-040 | Verificação independente de artefatos compilados | `omega_platform/artifact_verifier.py` (criar)<br>`omega_platform/manifest.py` (alterar/revalidar) | `testes/acceptance/test_om040.py` (criar) | `roadmap/evidence/om040.json` (criar) |

## Fase 3

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-041 | Interface unificada de problemas e objetivos | `omega_agent/problem.py` (criar)<br>`omega_agent/integration.py` (integrar) | `testes/acceptance/test_om041.py` (criar) | `roadmap/evidence/om041.json` (criar) |
| OM-042 | Representação de estados de raciocínio | `omega_agent/reasoning_state.py` (criar) | `testes/acceptance/test_om042.py` (criar) | `roadmap/evidence/om042.json` (criar) |
| OM-043 | Planejador hierárquico de tarefas | `omega_agent/hierarchical_planner.py` (criar) | `testes/acceptance/test_om043.py` (criar) | `roadmap/evidence/om043.json` (criar) |
| OM-044 | Planejamento por busca e avaliação de estados | `omega_agent/search.py` (criar) | `testes/acceptance/test_om044.py` (criar) | `roadmap/evidence/om044.json` (criar) |
| OM-045 | Raciocínio simbólico com regras de inferência | `omega_agent/inference.py` (criar) | `testes/acceptance/test_om045.py` (criar) | `roadmap/evidence/om045.json` (criar) |
| OM-046 | Raciocínio probabilístico calibrado | `omega_agent/calibration.py` (criar) | `testes/acceptance/test_om046.py` (criar) | `roadmap/evidence/om046.json` (criar) |
| OM-047 | Integração neural-simbólica bidirecional | `omega_agent/neurosymbolic.py` (criar)<br>`omega_nextorch/pipeline.py` (alterar/revalidar)<br>`omega_agent/integration.py` (integrar) | `testes/acceptance/test_om047.py` (criar) | `roadmap/evidence/om047.json` (criar) |
| OM-048 | Detecção de contradições e premissas ausentes | `omega_agent/consistency.py` (criar) | `testes/acceptance/test_om048.py` (criar) | `roadmap/evidence/om048.json` (criar) |
| OM-049 | Gerenciamento de hipóteses concorrentes | `omega_agent/hypotheses.py` (criar) | `testes/acceptance/test_om049.py` (criar) | `roadmap/evidence/om049.json` (criar) |
| OM-050 | Metacognição operacional | `omega_agent/metacognition.py` (criar) | `testes/acceptance/test_om050.py` (criar) | `roadmap/evidence/om050.json` (criar) |
| OM-051 | Orçamento adaptativo de raciocínio | `omega_agent/reasoning_budget.py` (criar) | `testes/acceptance/test_om051.py` (criar) | `roadmap/evidence/om051.json` (criar) |
| OM-052 | Planejamento de experimentos | `omega_agent/experiments.py` (criar) | `testes/acceptance/test_om052.py` (criar) | `roadmap/evidence/om052.json` (criar) |
| OM-053 | Aprendizado de heurísticas de busca | `omega_agent/learned_heuristics.py` (criar) | `testes/acceptance/test_om053.py` (criar) | `roadmap/evidence/om053.json` (criar) |
| OM-054 | Generalização composicional | `omega_agent/compositional.py` (criar) | `testes/acceptance/test_om054.py` (criar) | `roadmap/evidence/om054.json` (criar) |
| OM-055 | Detecção de distribuição desconhecida | `omega_agent/domain_shift.py` (criar) | `testes/acceptance/test_om055.py` (criar) | `roadmap/evidence/om055.json` (criar) |

## Fase 4

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-056 | Leitura e indexação semântica de repositórios | `omega_coder/repository_index.py` (criar) | `testes/acceptance/test_om056.py` (criar) | `roadmap/evidence/om056.json` (criar) |
| OM-057 | Tradução de requisitos em especificações executáveis | `omega_coder/specifications.py` (criar) | `testes/acceptance/test_om057.py` (criar) | `roadmap/evidence/om057.json` (criar) |
| OM-058 | Planejamento de alterações em múltiplos arquivos | `omega_coder/change_plan.py` (criar) | `testes/acceptance/test_om058.py` (criar) | `roadmap/evidence/om058.json` (criar) |
| OM-059 | Geração de código Ômega, Python, C e Lean | `omega_coder/generation.py` (criar) | `testes/acceptance/test_om059.py` (criar) | `roadmap/evidence/om059.json` (criar) |
| OM-060 | Editor estruturado por AST | `omega_coder/ast_editor.py` (criar) | `testes/acceptance/test_om060.py` (criar) | `roadmap/evidence/om060.json` (criar) |
| OM-061 | Geração automática de testes | `omega_coder/test_generation.py` (criar) | `testes/acceptance/test_om061.py` (criar) | `roadmap/evidence/om061.json` (criar) |
| OM-062 | Reparo de falhas de compilação e execução | `omega_coder/repair.py` (criar) | `testes/acceptance/test_om062.py` (criar) | `roadmap/evidence/om062.json` (criar) |
| OM-063 | Reparo assistido por contraexemplos formais | `omega_coder/counterexamples.py` (criar) | `testes/acceptance/test_om063.py` (criar) | `roadmap/evidence/om063.json` (criar) |
| OM-064 | Síntese guiada por contratos e tipos | `omega_coder/contract_synthesis.py` (criar) | `testes/acceptance/test_om064.py` (criar) | `roadmap/evidence/om064.json` (criar) |
| OM-065 | Busca enumerativa, evolutiva e neural de programas | `omega_coder/program_search.py` (criar) | `testes/acceptance/test_om065.py` (criar) | `roadmap/evidence/om065.json` (criar) |
| OM-066 | Otimização de programas com equivalência verificada | `omega_coder/verified_optimization.py` (criar)<br>`omega/equivalence.py` (criar) | `testes/acceptance/test_om066.py` (criar) | `roadmap/evidence/om066.json` (criar) |
| OM-067 | Execução de testes em worktrees isoladas | `omega_coder/worktrees.py` (criar) | `testes/acceptance/test_om067.py` (criar) | `roadmap/evidence/om067.json` (criar) |
| OM-068 | Revisão automatizada de patches | `omega_coder/patch_review.py` (criar) | `testes/acceptance/test_om068.py` (criar) | `roadmap/evidence/om068.json` (criar) |
| OM-069 | Geração de pull requests auditáveis | `omega_coder/pull_requests.py` (criar) | `testes/acceptance/test_om069.py` (criar) | `roadmap/evidence/om069.json` (criar) |
| OM-070 | Integração de ferramentas externas com permissões | `omega_tools/capability_adapter.py` (criar)<br>`omega_tools/local_files.py` (integrar)<br>`omega_tools/memory.py` (integrar) | `testes/acceptance/test_om070.py` (criar) | `roadmap/evidence/om070.json` (criar) |

## Fase 5

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-071 | Memória episódica de tarefas e resultados | `omega_memory/episodes.py` (criar)<br>`omega_tools/memory.py` (integrar)<br>`omega_agent/runtime.py` (integrar) | `testes/acceptance/test_om071.py` (criar) | `roadmap/evidence/om071.json` (criar) |
| OM-072 | Memória semântica com recuperação híbrida | `omega_memory/retrieval.py` (criar) | `testes/acceptance/test_om072.py` (criar) | `roadmap/evidence/om072.json` (criar) |
| OM-073 | Base de conhecimento com proveniência | `omega_memory/knowledge.py` (criar) | `testes/acceptance/test_om073.py` (criar) | `roadmap/evidence/om073.json` (criar) |
| OM-074 | Deduplicação, versionamento e expiração de memórias | `omega_memory/lifecycle.py` (criar) | `testes/acceptance/test_om074.py` (criar) | `roadmap/evidence/om074.json` (criar) |
| OM-075 | Buffer de replay certificado | `omega_memory/certified_replay.py` (criar)<br>`nextorch/evolution/replay_buffer.py` (alterar/revalidar) | `testes/acceptance/test_om075.py` (criar) | `roadmap/evidence/om075.json` (criar) |
| OM-076 | Treinamento incremental com controles de regressão | `omega_learning/incremental.py` (criar) | `testes/acceptance/test_om076.py` (criar) | `roadmap/evidence/om076.json` (criar) |
| OM-077 | Detecção de esquecimento catastrófico | `omega_learning/forgetting.py` (criar) | `testes/acceptance/test_om077.py` (criar) | `roadmap/evidence/om077.json` (criar) |
| OM-078 | Currículo automático de dificuldade | `omega_learning/curriculum.py` (criar) | `testes/acceptance/test_om078.py` (criar) | `roadmap/evidence/om078.json` (criar) |
| OM-079 | Aprendizado ativo e seleção de exemplos | `omega_learning/active_learning.py` (criar) | `testes/acceptance/test_om079.py` (criar) | `roadmap/evidence/om079.json` (criar) |
| OM-080 | Distilação de soluções e trajetórias | `omega_learning/distillation.py` (criar) | `testes/acceptance/test_om080.py` (criar) | `roadmap/evidence/om080.json` (criar) |
| OM-081 | Transferência entre domínios | `omega_learning/transfer.py` (criar) | `testes/acceptance/test_om081.py` (criar) | `roadmap/evidence/om081.json` (criar) |
| OM-082 | Treinamento com feedback de verificadores | `omega_learning/verifier_feedback.py` (criar) | `testes/acceptance/test_om082.py` (criar) | `roadmap/evidence/om082.json` (criar) |
| OM-083 | Prevenção de contaminação de benchmarks | `omega_learning/data_splits.py` (criar) | `testes/acceptance/test_om083.py` (criar) | `roadmap/evidence/om083.json` (criar) |
| OM-084 | Versionamento de datasets e checkpoints | `omega_learning/versioning.py` (criar) | `testes/acceptance/test_om084.py` (criar) | `roadmap/evidence/om084.json` (criar) |
| OM-085 | Políticas de privacidade e retenção | `omega_memory/privacy.py` (criar)<br>`omega_tools/memory.py` (integrar) | `testes/acceptance/test_om085.py` (criar) | `roadmap/evidence/om085.json` (criar) |

## Fase 6

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-086 | API estável para modelos de raciocínio | `omega_nextorch/model_api.py` (criar)<br>`nextorch/model.py` (alterar/revalidar)<br>`omega_agent/integration.py` (integrar) | `testes/acceptance/test_om086.py` (criar) | `roadmap/evidence/om086.json` (criar) |
| OM-087 | Tokenizer e representação de código, provas e texto | `omega_nextorch/tokenizer.py` (criar) | `testes/acceptance/test_om087.py` (criar) | `roadmap/evidence/om087.json` (criar) |
| OM-088 | Treinamento supervisionado de programação e raciocínio | `omega_nextorch/supervised_training.py` (criar)<br>`nextorch/model.py` (alterar/revalidar) | `testes/acceptance/test_om088.py` (criar) | `roadmap/evidence/om088.json` (criar) |
| OM-089 | Geração condicionada por AST, tipos e contratos | `omega_nextorch/constrained_generation.py` (criar) | `testes/acceptance/test_om089.py` (criar) | `roadmap/evidence/om089.json` (criar) |
| OM-090 | Busca neural com verificador no ciclo | `omega_nextorch/verified_search.py` (criar)<br>`omega_nextorch/gate.py` (alterar/revalidar) | `testes/acceptance/test_om090.py` (criar) | `roadmap/evidence/om090.json` (criar) |
| OM-091 | Crescimento Net2Net com testes de preservação | `nextorch/evolution/net2net.py` (alterar/revalidar) | `testes/acceptance/test_om091.py` (criar) | `roadmap/evidence/om091.json` (criar) |
| OM-092 | Mecanismos de expansão e poda de capacidade | `omega_nextorch/capacity.py` (criar)<br>`nextorch/evolution/loop.py` (alterar/revalidar) | `testes/acceptance/test_om092.py` (criar) | `roadmap/evidence/om092.json` (criar) |
| OM-093 | Interpretabilidade com SAE e análise causal | `omega_nextorch/causal_analysis.py` (criar)<br>`nextorch/interpretability/sae.py` (alterar/revalidar) | `testes/acceptance/test_om093.py` (criar) | `roadmap/evidence/om093.json` (criar) |
| OM-094 | Estimativa de incerteza e abstenção | `omega_nextorch/uncertainty.py` (criar) | `testes/acceptance/test_om094.py` (criar) | `roadmap/evidence/om094.json` (criar) |
| OM-095 | Treinamento distribuído com checkpoints recuperáveis | `omega_nextorch/distributed_training.py` (criar) | `testes/acceptance/test_om095.py` (criar) | `roadmap/evidence/om095.json` (criar) |
| OM-096 | Suporte CPU, GPU e precisão mista | `omega_nextorch/devices.py` (criar)<br>`nextorch/synthesis/triton_kernels.py` (alterar/revalidar) | `testes/acceptance/test_om096.py` (criar) | `roadmap/evidence/om096.json` (criar) |
| OM-097 | Avaliação de eficiência de inferência | `omega_nextorch/inference_metrics.py` (criar) | `testes/acceptance/test_om097.py` (criar) | `roadmap/evidence/om097.json` (criar) |
| OM-098 | Roteamento entre especialistas e modelos | `omega_nextorch/routing.py` (criar) | `testes/acceptance/test_om098.py` (criar) | `roadmap/evidence/om098.json` (criar) |
| OM-099 | Prevenção de reward hacking e overfitting ao verificador | `omega_nextorch/reward_integrity.py` (criar) | `testes/acceptance/test_om099.py` (criar) | `roadmap/evidence/om099.json` (criar) |
| OM-100 | Benchmark neural versus métodos simbólicos | `omega_bench/neural_symbolic.py` (criar) | `testes/acceptance/test_om100.py` (criar) | `roadmap/evidence/om100.json` (criar) |

## Fase 7

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-101 | Inventário formal de componentes modificáveis | `omega_evolution/component_registry.py` (criar) | `testes/acceptance/test_om101.py` (criar) | `roadmap/evidence/om101.json` (criar) |
| OM-102 | Motor de propostas de melhoria | `omega_evolution/proposals.py` (criar) | `testes/acceptance/test_om102.py` (criar) | `roadmap/evidence/om102.json` (criar) |
| OM-103 | Modificação de código em ramificações isoladas | `omega_evolution/isolated_patches.py` (criar)<br>`omega_coder/worktrees.py` (criar) | `testes/acceptance/test_om103.py` (criar) | `roadmap/evidence/om103.json` (criar) |
| OM-104 | Geração de novas heurísticas de síntese | `omega_evolution/synthesis_heuristics.py` (criar) | `testes/acceptance/test_om104.py` (criar) | `roadmap/evidence/om104.json` (criar) |
| OM-105 | Otimização do próprio compilador | `omega_evolution/compiler_tuning.py` (criar) | `testes/acceptance/test_om105.py` (criar) | `roadmap/evidence/om105.json` (criar) |
| OM-106 | Otimização do planejador e do mecanismo de busca | `omega_evolution/planner_tuning.py` (criar) | `testes/acceptance/test_om106.py` (criar) | `roadmap/evidence/om106.json` (criar) |
| OM-107 | Ajuste de hiperparâmetros sob orçamento | `omega_evolution/hyperparameters.py` (criar) | `testes/acceptance/test_om107.py` (criar) | `roadmap/evidence/om107.json` (criar) |
| OM-108 | Propostas de mudança de arquitetura neural | `omega_evolution/architecture_search.py` (criar) | `testes/acceptance/test_om108.py` (criar) | `roadmap/evidence/om108.json` (criar) |
| OM-109 | Seleção estatística de melhorias | `omega_evolution/statistics.py` (criar) | `testes/acceptance/test_om109.py` (criar) | `roadmap/evidence/om109.json` (criar) |
| OM-110 | Portão independente de promoção | `omega_evolution/promotion.py` (criar) | `testes/acceptance/test_om110.py` (criar) | `roadmap/evidence/om110.json` (criar) |
| OM-111 | Rollback transacional de versões | `omega_evolution/rollback.py` (criar) | `testes/acceptance/test_om111.py` (criar) | `roadmap/evidence/om111.json` (criar) |
| OM-112 | Detecção de regressão de segurança e capacidade | `omega_evolution/regressions.py` (criar) | `testes/acceptance/test_om112.py` (criar) | `roadmap/evidence/om112.json` (criar) |
| OM-113 | Árvore genealógica de versões e experimentos | `omega_evolution/lineage.py` (criar) | `testes/acceptance/test_om113.py` (criar) | `roadmap/evidence/om113.json` (criar) |
| OM-114 | Limites de recursos para ciclos evolutivos | `omega_evolution/resource_limits.py` (criar) | `testes/acceptance/test_om114.py` (criar) | `roadmap/evidence/om114.json` (criar) |
| OM-115 | Parada por estagnação, risco ou incerteza | `omega_evolution/stopping.py` (criar) | `testes/acceptance/test_om115.py` (criar) | `roadmap/evidence/om115.json` (criar) |

## Fase 8

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-116 | Interface de ferramentas com contratos tipados | `omega_tools/contracts.py` (criar)<br>`omega_tools/local_files.py` (integrar)<br>`omega_tools/memory.py` (integrar) | `testes/acceptance/test_om116.py` (criar) | `roadmap/evidence/om116.json` (criar) |
| OM-117 | Navegação e recuperação de informação | `omega_tools/web.py` (criar) | `testes/acceptance/test_om117.py` (criar) | `roadmap/evidence/om117.json` (criar) |
| OM-118 | Leitura estruturada de PDFs e documentos | `omega_tools/documents.py` (criar) | `testes/acceptance/test_om118.py` (criar) | `roadmap/evidence/om118.json` (criar) |
| OM-119 | Interpretação de imagens e diagramas | `omega_tools/vision.py` (criar) | `testes/acceptance/test_om119.py` (criar) | `roadmap/evidence/om119.json` (criar) |
| OM-120 | Entrada e saída de áudio opcionais | `omega_tools/audio.py` (criar) | `testes/acceptance/test_om120.py` (criar) | `roadmap/evidence/om120.json` (criar) |
| OM-121 | Execução de código e notebooks isolados | `omega_tools/notebooks.py` (criar) | `testes/acceptance/test_om121.py` (criar) | `roadmap/evidence/om121.json` (criar) |
| OM-122 | Interface com bancos de dados | `omega_tools/database.py` (criar) | `testes/acceptance/test_om122.py` (criar) | `roadmap/evidence/om122.json` (criar) |
| OM-123 | Integração com Git, CI e issues | `omega_tools/git_ci.py` (criar) | `testes/acceptance/test_om123.py` (criar) | `roadmap/evidence/om123.json` (criar) |
| OM-124 | Ambientes simulados para planejamento | `omega_tools/simulation.py` (criar) | `testes/acceptance/test_om124.py` (criar) | `roadmap/evidence/om124.json` (criar) |
| OM-125 | Políticas de aprovação de ações externas | `omega_tools/approvals.py` (criar) | `testes/acceptance/test_om125.py` (criar) | `roadmap/evidence/om125.json` (criar) |

## Fase 9

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-126 | Modelo de ameaças para agentes e autoedição | `docs/THREAT_MODEL_AGENT.md` (criar) | `testes/acceptance/test_om126.py` (criar) | `roadmap/evidence/om126.json` (criar) |
| OM-127 | Controle de acesso por capacidades | `omega_security/capabilities.py` (criar)<br>`omega_security/encoding.py` (integrar) | `testes/acceptance/test_om127.py` (criar) | `roadmap/evidence/om127.json` (criar) |
| OM-128 | Separação entre proponente, verificador e promotor | `omega_security/roles.py` (criar)<br>`omega_evolution/promotion.py` (criar) | `testes/acceptance/test_om128.py` (criar) | `roadmap/evidence/om128.json` (criar) |
| OM-129 | Defesa contra prompt injection e dados adversariais | `omega_security/untrusted_data.py` (criar) | `testes/acceptance/test_om129.py` (criar) | `roadmap/evidence/om129.json` (criar) |
| OM-130 | Proteção de segredos e credenciais | `omega_security/secrets.py` (criar) | `testes/acceptance/test_om130.py` (criar) | `roadmap/evidence/om130.json` (criar) |
| OM-131 | Auditoria imutável de decisões e ações | `omega_security/audit.py` (criar) | `testes/acceptance/test_om131.py` (criar) | `roadmap/evidence/om131.json` (criar) |
| OM-132 | Desligamento e revogação de permissões | `omega_security/revocation.py` (criar) | `testes/acceptance/test_om132.py` (criar) | `roadmap/evidence/om132.json` (criar) |
| OM-133 | Controle de objetivos e limites de autonomia | `omega_security/objectives.py` (criar) | `testes/acceptance/test_om133.py` (criar) | `roadmap/evidence/om133.json` (criar) |
| OM-134 | Monitoramento de comportamento e anomalias | `omega_security/anomalies.py` (criar) | `testes/acceptance/test_om134.py` (criar) | `roadmap/evidence/om134.json` (criar) |
| OM-135 | Avaliação adversarial independente | `omega_security/adversarial.py` (criar) | `testes/acceptance/test_om135.py` (criar) | `roadmap/evidence/om135.json` (criar) |

## Fase 10

| Tarefa | Entrega | Implementação | Testes | Evidências |
|---|---|---|---|---|
| OM-136 | Harness unificado de benchmarks | `omega_bench/harness.py` (criar) | `testes/acceptance/test_om136.py` (criar) | `roadmap/evidence/om136.json` (criar) |
| OM-137 | Conjuntos de tarefas de programação inéditas | `omega_bench/programming.py` (criar) | `testes/acceptance/test_om137.py` (criar) | `roadmap/evidence/om137.json` (criar) |
| OM-138 | Benchmarks de prova matemática | `omega_bench/mathematics.py` (criar) | `testes/acceptance/test_om138.py` (criar) | `roadmap/evidence/om138.json` (criar) |
| OM-139 | Benchmarks de generalização e transferência | `omega_bench/generalization.py` (criar) | `testes/acceptance/test_om139.py` (criar) | `roadmap/evidence/om139.json` (criar) |
| OM-140 | Experimentos de autoaperfeiçoamento longitudinal | `omega_bench/longitudinal.py` (criar) | `testes/acceptance/test_om140.py` (criar) | `roadmap/evidence/om140.json` (criar) |
| OM-141 | Ablações de memória, Nextorch, Lean e busca | `omega_bench/ablations.py` (criar) | `testes/acceptance/test_om141.py` (criar) | `roadmap/evidence/om141.json` (criar) |
| OM-142 | Telemetria de CPU, GPU, RAM, energia e tempo | `omega_bench/telemetry.py` (criar) | `testes/acceptance/test_om142.py` (criar) | `roadmap/evidence/om142.json` (criar) |
| OM-143 | Rastreabilidade de datasets, seeds e modelos | `omega_bench/provenance.py` (criar) | `testes/acceptance/test_om143.py` (criar) | `roadmap/evidence/om143.json` (criar) |
| OM-144 | Relatórios estatísticos e análise de falhas | `omega_bench/statistics.py` (criar) | `testes/acceptance/test_om144.py` (criar) | `roadmap/evidence/om144.json` (criar) |
| OM-145 | Painel de progresso e maturidade | `omega_bench/dashboard.py` (criar) | `testes/acceptance/test_om145.py` (criar) | `roadmap/evidence/om145.json` (criar) |
| OM-146 | Infraestrutura de execução distribuída | `omega_platform/workers.py` (criar)<br>`omega_platform/scheduler.py` (criar) | `testes/acceptance/test_om146.py` (criar) | `roadmap/evidence/om146.json` (criar) |
| OM-147 | Cache de provas e artefatos por hash | `omega_platform/content_cache.py` (criar)<br>`omega_platform/proof_cache.py` (criar) | `testes/acceptance/test_om147.py` (criar) | `roadmap/evidence/om147.json` (criar) |
| OM-148 | Políticas de custo, quota e interrupção | `omega_platform/quotas.py` (criar) | `testes/acceptance/test_om148.py` (criar) | `roadmap/evidence/om148.json` (criar) |
| OM-149 | Empacotamento, releases e documentação de API | `pyproject.toml` (alterar/revalidar)<br>`MANIFEST.in` (alterar/revalidar)<br>`scripts/package.py` (alterar/revalidar)<br>`docs/API_3_0.md` (criar) | `testes/acceptance/test_om149.py` (criar) | `roadmap/evidence/om149.json` (criar) |
| OM-150 | Avaliação externa e revisão de resultados | `omega_bench/reproduction.py` (criar)<br>`docs/EXTERNAL_REVIEW.md` (criar) | `testes/acceptance/test_om150.py` (criar) | `roadmap/evidence/om150.json` (criar) |

## Critérios que precisam de trabalho além de escrever arquivos

- OM-026–OM-040: especificações e provas devem cobrir o subconjunto declarado, compilar em Lean e rejeitar certificados/admissões inválidos.
- OM-053–OM-055, OM-076–OM-100, OM-104–OM-109 e OM-136–OM-150: ganhos, generalização e eficiência precisam de experimentos retidos e resultados reproduzíveis. Implementar o harness não demonstra esses ganhos.
- OM-095–OM-096, OM-119–OM-120 e OM-142–OM-146: dependem também de hardware, modelos, dados e ambientes de avaliação adequados.
- OM-110, OM-128, OM-135 e OM-150: independência e revisão externa não podem ser produzidas pela autoaprovação do proponente.
- O arquivo único é regenerado a partir dos fontes; não deve ser editado manualmente para simular cobertura. Quantidade de linhas não é critério de conclusão.

## Contagem desta proposta

{"tasks": 150, "distinct_paths": 672, "existing": 81, "proposed_new": 591}

Os números de arquivos existentes/novos usam o planejamento original como base.
A entrega inclui os auxiliares de integração, testes e 150 planos; nenhum estado passa a aceito por essas contagens.
Execução, resultados reais e novas evidências de aceite continuam adiados por solicitação do usuário.

## Entrega de validação sem execução

Os 150 planos e os formatos dos relatórios estão em [validation/README.md](../validation/README.md).
Os 132 descritores novos em `roadmap/evidence/` são pendências, sem resultados ou aceite.
Os relatórios históricos de OM-001 a OM-018 foram preservados e não validam esta revisão.
