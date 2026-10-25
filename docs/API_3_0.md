# API proposta para a próxima geração

Versão publicada do projeto: 2.0.0. Os módulos desta entrega são fontes ainda
sem validação; a existência da API não anuncia conclusão dos 150 aceites.

## Linguagem e execução

- `omega.stdlib`: fila, pilha e mapa racionais limitados; `install_library`
  copia `omega_selfhost/stdlib.omega` para uma raiz explícita de módulos.
- `omega_selfhost.native_backend`: política de otimização C por build.
- `omega_selfhost.wasm_backend`: emissão e execução do subconjunto escalar i64.
- `omega.trace`, `omega.debugger`, `omega.profiler`: avaliação pura e replay.
- `omega.package_lock`, `omega.packages`: resolução local determinística e hashes.
- `omega_platform.scheduler`: lotes readonly com reservas de CPU/memória.
- `omega_platform.workers`: transporte autenticado configurado pelo host.

O runtime nativo usa uma arena de vida do processo, liberada após limpar GMP.
Não se trata de um coletor de lixo incremental: alocações intermediárias são
retidas até o encerramento/reset de uma região e o orçamento pode recusar
programas longos. Um reset só pode ocorrer quando não houver referências vivas.

## Agente e programação

`omega_agent` contém contratos de problemas/objetivos, registros de premissas,
planejamento, busca, inferência Horn, calibração, hipóteses e critérios de parada.
`CognitiveAgent` compõe um adaptador de modelo limitado com um checker independente.
`omega_coder` fornece indexação estática, especificações, planos, geração,
edição de spans AST, síntese finita, reparo, worktrees e PRs com aprovação.
Índices sintáticos não resolvem todos os imports/chamadas dinâmicos de Python,
C ou Lean. Geradores devolvem candidatos, sem executá-los no processo do host.

## Memória, aprendizado e modelos

`omega_memory` inclui episódios SQLite, recuperação lexical/vetorial,
proveniência, expiração e replay. `omega_learning` contém treino incremental
em cópias, esquecimento, currículo, seleção ativa, distilação e splits.
`omega_nextorch` acrescenta protocolo de modelos, tokenizer de bytes,
treinamento, decoding condicionado, incerteza, roteamento e intervenções.
Treino distribuído exige processo/grupo explicitamente inicializado pelo host.
WASM, PDF e assinaturas usam dependências opcionais do extra `tools`, sem
instalação automática. Visão/áudio usam providers configurados pelo host;
não há pesos multimodais novos nesta entrega.

## Evolução, ferramentas e governança

`omega_evolution` separa propostas, medidas, regressões, promoção e rollback.
`omega_tools` fornece contratos e adaptadores de rede, documentos, visão,
áudio, notebooks, SQLite, Git/CI e simulação. Ações externas exigem capacidades
válidas; alterações sensíveis também exigem aprovações externas autenticadas.
`omega_security` contém verificação Ed25519, revogação, papéis, auditoria,
objetivos, redação e monitoramento. O dono da configuração é parte confiável;
um agente não pode escolher seu próprio autenticador permissivo em produção.

## Medição e aceite

`omega_bench` recebe solvers host confiáveis que isolam qualquer código candidato.
Somente o input público chega ao solver; respostas ocultas ficam no oráculo.
Há harness, tarefas, estatísticas, ablações, métricas, genealogia e reprodução.
Valores de energia/GPU indisponíveis permanecem `None`; não são inventados.
Ganhos de generalização, ausência de esquecimento e autoaperfeiçoamento precisam
ser demonstrados posteriormente. Esta entrega não os declara demonstrados.

O bundle `omega/omega_3_monolith.py` é regenerado dos fontes. Não o edite à mão.
O ledger distingue `source_written_pending_validation` de implementação aceita.

## Entrada para raciocínio finito

`omega agent infer problema.json` calcula fecho Horn com testemunhas explícitas.
`omega agent plan problema.json` ordena um DAG de tarefas e lista as prontas.
`omega agent synthesize problema.json` enumera expressões racionais sob orçamento
para exemplos finitos. Também estão disponíveis por `python -m omega_agent`.
Esses comandos não invocam serviços externos, não alteram o próprio código e
não declaram provas universais a partir de exemplos. Sua execução também ficou
adiada nesta entrega de fontes.
