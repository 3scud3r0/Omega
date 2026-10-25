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

## Integração do supervisor, ainda sem execução

A montagem concreta fica em `omega_agent.integration`. `boolean_problem(task)`
converte a tarefa `{id, arity, outputs}` no contrato
`omega-nextorch:exact-bounded-truth-table:1`. `boolean_agent(model, ...)` conecta
um modelo com protocolo `propose`, o checker `omega_nextorch.gate.certify`, o
verificador de capacidades, auditoria, ferramentas opcionais e um destino de
metadados episódicos. `NextorchBooleanAdapter` implementa o lado das propostas.
O checker dessa montagem aceita somente esse contrato, sem restrições extras;
não certifica minimalidade, objetivos de texto livre ou outros domínios.

O host entrega um `Goal` e uma capacidade assinada com ação `agent.solve`.
O campo `subject` dessa capacidade é obrigatório e deve ser igual a
`goal.subject(problem.fingerprint())`; `goal.authorized_by` identifica o emissor
configurado da capacidade. Trocar entradas, objetivo, contrato de sucesso ou
limite de ações invalida a vinculação. As propostas e as entradas do checker
são cópias de dados; o resultado registra o checker usado e `promoted=False`.
Metadados gravados em `EpisodeStore` são marcados como sensíveis e não incluem
as entradas, as propostas ou os conteúdos brutos de ferramentas.

`omega_security.encoding` define a representação compartilhada: JSON UTF-8,
chaves ordenadas, sem espaços, valores finitos, sem chaves repetidas e com
limites de bytes, nós e profundidade. O tamanho é contabilizado antes de gerar
a string serializada. Assinaturas devem usar esses bytes exatos. Chaves
privadas e emissão de capacidades continuam fora destes módulos.

### Pedidos de ferramentas

Um modelo pode devolver um objeto de dados com exatamente estes campos:

```json
{"kind":"tool_request","name":"files.read_text","arguments":{"path":"/raiz/arquivo.txt"}}
```

`decode_proposal` converte esse objeto em `ToolRequest`. O callback confiável
`authorize_tool(goal_subject, request)` recebe uma cópia do pedido concreto do
adaptador, com os campos `tool`, `action`, `arguments` e `principal`. Ele deve
consultar a política do supervisor e devolver `ToolAuthorization(capability,
approval)` ou `None`. O modelo não fornece nem escolhe a capacidade. `None`
encerra a rodada como `awaiting_approval`, com o pedido e seu hash para revisão;
a ferramenta ainda não é chamada. Esta interface não persiste nem retoma uma
sessão automaticamente: o host deve reautorizar a continuação explicitamente.

`CapabilityAdapter` exige o contrato dos argumentos e da resposta, verifica
cada `path_field`, aplica um limite de chamadas e sela o registro após iniciar
seu uso. Uma capacidade com `subject` precisa corresponder ao digest do pedido
concreto; capacidades sem esse campo continuam sendo escopos concedidos pelo
host, com ações explícitas, raiz absoluta, expiração e revogação. Uma capacidade
vinculada a um assunto não pode ser usada por uma API que omite esse assunto.
Ações mutáveis conhecidas exigem `approval_required=True` e um `ApprovalGate`.
A aprovação vincula todos os argumentos, tem prazo e exige um ator diferente
do principal executor. O adaptador audita hashes e estados de início/fim/falha,
sem registrar os argumentos ou saídas brutas.

`register_files(adapter, root, writable=False)` registra leitura UTF-8 limitada
com operações ancoradas em descritores e sem seguir symlinks. O modo de escrita
é uma opção do host e exige aprovação e o hash esperado do arquivo existente;
não oferece criação de arquivos nessa interface. O root configurado e o root
da capacidade restringem conjuntamente o acesso. A comparação do hash e a
substituição não constituem CAS contra escritores externos não coordenados;
o host deve serializar as alterações de um mesmo arquivo.
`register_memory(adapter, private_memory, consent_resolver)` registra somente
recuperação por `PrivateMemory`, com retenção e consentimento conferidos pela
política configurada; não expõe treino ou exportação.

Saídas de ferramentas recebem `authority=False`. Por padrão, só seus hashes
retornam ao contexto do modelo. `observe_tool` é um filtro do host para fornecer
uma observação selecionada; ele não recebe autoridade para alterar o objetivo.
O contexto acumulado e o número de passos continuam limitados. Deadlines do
agente são cooperativos, conferidos antes/depois dos adaptadores; interromper
um callback bloqueado exige o worker/processo isolado configurado pelo host.

### RPC de workers e cancelamento

`Coordinator.dispatch` admite um lote limitado antes de enviar o primeiro RPC,
confere capacidades, distribui jobs pelas vagas configuradas e preserva a ordem
dos resultados. Quotas de CPU e número de jobs valem para a vida da instância;
reservas de memória e concorrência são compartilhadas entre chamadas. O host
renova essas instâncias e quotas por política, sem conceder esse controle ao
modelo. `capabilities` aceita chaves `(worker_id, job_id)` para capacidades de
um job, ou `worker_id` para um escopo do host que autorize vários jobs.
`job_subject(job)` fornece o hash para uma capacidade opcionalmente vinculada.

O transporte tem assinatura `transport(endpoint, request, *, timeout)` e deve
impor timeout de I/O, TLS e a identidade do endpoint configurado. O envelope
`omega-worker-request-1` contém destino, `request_id`, job, seu hash e a
capacidade serializada. O servidor verifica a ação `worker.execute:<id>` e os
escopos de leitura/execução. A resposta `omega-worker-response-1` vincula worker,
job, hash e `request_id`; o cliente confere esses campos e a autenticação do
host. `verify_response(worker, response, signature_verifier)` oferece a
conferência dos bytes assinados para esse autenticador. Não há retentativas
automáticas de execução em caso de falha de transporte.

`WorkerServer` compartilha quotas e rejeita a repetição de `request_id` durante
a vida da instância. Registra um callback de revogação e um timer de expiração,
que sinalizam o evento de cancelamento observado pelo supervisor do sandbox.
O callback é removido após a execução. Revogações remotas precisam chegar ao
registro desse servidor pelo serviço configurado pelo host. Replay de RPCs e
aprovações de ferramentas usam estado em memória: reinícios exigem persistência
externa antes de permitir reutilização de tickets. Os artefatos montados devem
ser imutáveis e pertencentes ao supervisor; o hash do job vincula caminhos,
argumentos e orçamento, não mede sozinho o conteúdo de cada mount.

### Promoção e ponteiro de versões

`PromotionGate.prepare` gera os bytes que verificador e promotor independentes
devem examinar e assinar. O payload inclui proposta completa, baseline, versão
alvo, caminhos, resultados declarados e manifesto de artefatos. Esse manifesto
contém `patch_sha256`, `baseline_version`, `baseline_artifacts_sha256` e um mapa
`files` de caminhos relativos para hashes completos. O registry rejeita caminhos
fora do componente e sobreposição de componentes mutáveis com protegidos.

`Attestation` inclui `expires` nos bytes assinados; promoção exige prazo nos
dois registros e três atores distintos. `PromotionDecision` é um envelope de
dados, sem flag que conceda autoridade. `Versions.activate` chama novamente
`PromotionGate.authorize` dentro da transação, compara a baseline e seu hash,
confere os artefatos e executa o healthcheck do host antes de publicar o ponteiro.
`ArtifactVerifier.promotion` fornece a conferência dos arquivos do manifesto;
isso confere integridade de bytes, sem provar equivalência entre fonte e binário.
Os atestadores independentes continuam responsáveis pela verdade das evidências.

O root privado de `Versions` precisa de `promotion_gate` e auditoria. Na primeira
ativação, exige `initial_version` junto de `initial_artifacts_sha256`, definidos
pelo supervisor a partir da versão estável. O ponteiro novo usa formato
`omega-version-pointer-1`; ponteiros antigos exigem migração explícita. Um ledger
persistente consome a autorização antes da escrita do ponteiro. Falhas de escrita
ou auditoria tentam restaurar o ponteiro anterior e mantêm o ticket consumido.
Um crash pode exigir recuperação pelo supervisor; esta transação não substitui
um protocolo de deploy de todos os serviços em execução.

`rollback(authorization, healthcheck)` exige um verificador independente
`authorize_rollback(action, authorization)` fornecido pelo host. Esse callback
revalida, sem consumir, a autorização do alvo concreto e é chamado antes e após
o healthcheck. Sem essa configuração, rollback manual é recusado. O retorno por
falha da transação usa o estado anterior já capturado. Nenhuma dessas operações
é invocada automaticamente pelo agente ou pela importação dos módulos.

Esta continuação altera apenas fontes e documentação. Não foram executados
imports dos módulos novos, builds, testes, benchmarks ou avaliações de segurança.
Os estados de aceite do backlog permanecem pendentes.

## Entrega de testes e revisão da OM-018

Os fontes de testes e planos foram acrescentados posteriormente em
`testes/acceptance/`, `testes/lean/` e `validation/`, sem execução. O executor
`scripts/validate-roadmap.py` só inicia testes com `--execute`; os descritores
novos em `roadmap/evidence/` têm status `not_run` e resultados nulos. O histórico
de execuções anteriores foi preservado e não valida estes fontes modificados.

A revisão da OM-018 acrescenta `Registry.specialize` e `Specialization`, com
vinculação explícita de dimensões e identificador determinístico. Templates
permanecem fechados e imutáveis, sem captura ou recursão; argumentos continuam
sendo avaliados estritamente, inclusive quando não usados pelo corpo.
`ExpansionLimits` limita bytes de entrada/saída, passos, profundidade, bindings,
chamadas e especializações. Os limites constam do manifesto e são reaplicados
na reconstrução da proveniência. `Registry.from_bytes` permite ao build usar a
mesma captura dos templates que será preservada como artefato, sem reabertura.

Os comandos `generic-ir` e `generic-build` aceitam `--max-expansion-steps`,
`--max-specializations` e `--max-generic-calls`. Os defaults preservam as cotas
anteriores; não é permitido ampliar além dos tetos da API. Manifestos de builds
genéricos anteriores à revisão devem ser reconstruídos. A correção dessa
revisão ainda depende de executar os testes antigos e novos e o checker Lean.
