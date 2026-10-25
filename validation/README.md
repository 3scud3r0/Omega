# Testes e validação OM-001 a OM-150

Esta entrega contém fontes de testes, planos e um executor. Nada foi executado
para produzir resultados. Os JSON novos em `roadmap/evidence/om019.json` até
`om150.json` são descritores `not_run`, com resultados e aceite nulos. Os
relatórios antigos foram preservados como histórico e não validam as mudanças.

A OM-018 foi refeita com contratos de especialização por dimensões, identidades
determinísticas, limites de expansão configuráveis, captura única dos templates
no build e registro/reprodução desses limites na proveniência. Os testes
anteriores continuam presentes; os novos estão em `test_om018.py`.

## Arquivos

- `catalog.json`: índice das 150 tarefas e dos testes compartilhados.
- `plans/om001.json` até `plans/om150.json`: critério de aceite, fontes, testes,
  argv revisável, perfil de recursos e obrigações além dos ensaios funcionais.
- `plan.schema.json`, `report.schema.json`, `pending.schema.json`: formatos dos
  planos, relatórios reais e descritores pendentes. Não são relatórios de êxito.
- `../testes/acceptance/`: ensaios Python para OM-018 a OM-150, fixtures,
  integração do supervisor e executor. Os testes anteriores de OM-001 a OM-018
  permanecem em `testes/foundation/`.
- `../testes/lean/OM026.lean` até `OM035.lean`: exemplos/propriedades formais no
  subconjunto declarado. OM-031 mantém explícita a hipótese de implementação.
- `../testes/acceptance/memory_harness.c`: ensaios de arena de memória; o teste
  correspondente compila e executa também com ASan/UBSan no ambiente isolado.
- `../scripts/validate-roadmap.py`: execução futura por tarefa ou do conjunto.

## Próxima etapa, quando formos executar

Preparar previamente o ambiente descrito em `scripts/setup.sh`, com Python
3.12, dependências CPU/dev/tools, C/GMP, bubblewrap e Lean/Mathlib fixados.
O executor não instala dependências nem baixa modelos automaticamente. Falta
de ferramentas ou dependências deve aparecer como falha de infraestrutura.
Providers remotos não são contatados por testes automáticos; testes de
contratos usam providers locais ou fixtures. GPU ausente produz skip explícito,
que torna a validação da tarefa incompleta, não aprovada.

Os comandos abaixo são instruções para a próxima etapa; não foram executados:

```bash
# Exibir o plano sem iniciar testes
.venv/bin/python scripts/validate-roadmap.py --task OM-018

# Executar primeiro os testes do executor e a integração compartilhada
.venv/bin/python -m pytest testes/acceptance/test_validation_runner.py testes/acceptance/test_supervised_flow.py -q

# Executar uma tarefa explicitamente
.venv/bin/python scripts/validate-roadmap.py --task OM-018 --execute

# Executar os planos das 150 tarefas explicitamente
.venv/bin/python scripts/validate-roadmap.py --all --execute

# Regressão geral, incluindo todos os testes anteriores e novos
.venv/bin/python -m pytest testes -q --junitxml=artifacts/full-regression.xml
```

O runner executa somente os arquivos pytest revisados do plano, com orçamentos
de tempo/CPU/memória. Os próprios testes devem isolar qualquer programa
candidato. A execução de testes Python confiáveis acontece no host: o runner
não transforma código arbitrário em confiável por constar em um plano.

Cada execução cria um diretório exclusivo em `artifacts/validation/<run-id>/`
com commit, indicação de checkout modificado, hashes das entradas, JUnit,
stdout/stderr redigidos e relatórios por tarefa. Resultados negativos e skips
ficam preservados. Arquivos de entrada ausentes, zero testes, JUnit ausente,
alterações das entradas durante o ensaio e erros de infraestrutura não contam
como aprovação. Logs usam a redação disponível, sem promessa de sigilo universal.

O status `checks_passed_acceptance_pending` significa somente que os checks
executados passaram sem skips. `acceptance_passed` e revisão independente
permanecem nulos. O runner não altera o ledger, não mescla PRs, não ativa versões
e não converte testes sintéticos em resultados científicos. As obrigações
adicionais de cada plano exigem avaliações reais posteriores.
