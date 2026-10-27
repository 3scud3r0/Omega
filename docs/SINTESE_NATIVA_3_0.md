# Síntese racional com execução nativa e replay

Este fluxo integra a síntese finita da OM-064, geração de fontes Ômega e
compilação/execução/verificação existentes. Não muda a versão publicada 2.0.0
nem aceita automaticamente as tarefas do roteiro 3.0.

```sh
bash scripts/setup.sh
export OMEGA_LEAN=/workspace/.tools/lean-4.19.0-linux/bin/lean

.venv/bin/python -m omega agent synthesize-native exemplos/sintese_racional.json \
  --max-size 3 --max-candidates 100 --saida artifacts/sintese-racional

.venv/bin/python -m omega agent audit-synthesis artifacts/sintese-racional
```

Use um diretório novo. O problema contém `variables`, `constants` opcional,
`examples` e `validation_examples`, conforme o exemplo incluído. Valores são
inteiros ou strings de racionais exatos; floats e bools são recusados. Variáveis
são identificadores únicos. Inputs repetidos ou compartilhados entre treino e
validação são rejeitados após normalização racional (por exemplo, 1 e 2/2).

A busca enumera somente árvores de dados com variáveis, constantes e operações
`+`, `-`, `*`, sob limites de candidatos, nós, tempo, CPU, memória e saídas.
Ela roda em um processo isolado sem rede; somente o runtime Python, dois
arquivos-fonte revisados e `search.json` de treino são montados. O repositório,
o ambiente do chamador e os casos reservados não são montados. A enumeração
é incremental: não materializa um produto cartesiano inteiro antes de aplicar
o limite de candidatos. O máximo de candidatos retidos é o orçamento global.

O primeiro candidato que satisfaz o treino é fechado em uma AST validada e
emitido com nomes locais próprios. Um único programa contém as instâncias dos
casos de treino e reservados. Seus targets não aparecem na fonte. O compilador
auto-hospedado produz C/GMP e binário, com análise de tipos e builds isolados.
O binário executa no sandbox e o kernel Lean confere os valores contra sua IR.
Um checker separado compara as saídas admitidas com todos os targets exatos.
Uma falha reservada rejeita o candidato, sem voltar à busca para ajustá-lo a
esse conjunto. O chamador deve manter um conjunto externo adicional para
medir generalização entre múltiplas execuções ou escolhas de configuração.

O diretório preserva problema normalizado, entrada da busca, AST candidata,
fonte Ômega, C, binário, proveniência, resultado nativo, admissão, relatório e
manifesto de hashes. Uma exceção preserva os artefatos parciais e um relatório
`failed`; limite esgotado é `exhausted`; saída divergente é `rejected`.
Somente `checks_passed` aprova os casos finitos. A CLI retorna 1 para falhas,
rejeição ou esgotamento. O envelope `ok` indica sucesso da operação de produzir
o relatório; inspecione `value.checks_passed` e o código de saída para o ensaio.

O auditor confere integridade e recusa symlinks e nomes fora da lista de
artefatos. Orçamentos gravados no arquivo não podem ampliar a política do
supervisor: por padrão, valem os mesmos tetos do fluxo original. O manifesto
global de build também registra os fontes de todos os novos subsistemas. Reexecuta a busca em sandbox, regenera a fonte, recompila em uma
pasta temporária, executa e verifica de novo, comparando casos, resultados e
alegações com o arquivo. Não executa o binário arquivado. Para vincular o
problema autorizado pelo supervisor, passe `--problem-sha256` com o hash do
problema normalizado conhecido antes da revisão. Hashes internos sem esse
vínculo não autenticam origem: modificar problema e manifesto juntos muda o
objeto auditado. O diretório deve pertencer ao supervisor e não deve ter
escritores concorrentes durante leitura/publicação; não é um armazenamento
transacional contra um dono adversarial.

Limites: até 32 variáveis, 64 constantes, 64 casos totais, 31 nós por expressão,
100 mil candidatos e 256 bits por racional de entrada. A expressão inferida
não vira automaticamente uma API genérica nem uma prova universal. A admissão
Lean verifica computações observadas no subconjunto existente: não demonstra
o refinamento geral do compilador/backend C (OM-031). Uma auditoria local não
substitui revisão externa independente (OM-150). Nenhum resultado promove
código, autoriza ferramentas externas ou anuncia inteligência geral.

# Pendências para declarar a versão 3.0 completa

A aprovação dos ensaios de CPU não demonstra todos os critérios das 150 tarefas.
Continuam necessários, conforme as obrigações dos planos em `validation/plans/`:

- GPU/CUDA real para paridade, precisão mista e Triton; este ambiente tem
  PyTorch CPU e não permite certificar essa parte por simulação.
- Descarregar a hipótese `NativeContract.implements` para o backend real e
  revisar os demais limites do subconjunto formalizado.
- Medir generalização, transferência, aprendizado contínuo, contribuições
  neurais e ganhos sucessivos de autoaperfeiçoamento em tarefas retidas, com
  baselines, custos equivalentes, estatísticas e resultados negativos.
- Configurar providers e infraestrutura reais quando aplicável (visão, áudio,
  treinamento e workers distribuídos), sem tratar fixtures como desempenho real.
- Reproduzir os marcos e aceitar suas evidências por revisores independentes.

Essas obrigações não são preenchidas com resultados sintéticos nem pela
alteração do número de versão. O fluxo acima é uma entrega funcional limitada.
