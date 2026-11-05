# Modos cognitivos e pipeline bicameral

O comando `omega cognition discover` separa propostas, evidência empírica e
admissão formal. O modo padrão é `strict`. Os comandos anteriores conservam
suas próprias políticas; a flag não transforma toda a linguagem em um sistema
formalmente verificado. Provas são relativas ao modelo, às premissas e à base
lógica declarada, não uma garantia de imunidade a falhas físicas ou de software.

```sh
# Prova em Lean antes de admitir a hipótese; executa uma especialização RV64.
.venv/bin/python -m omega cognition discover omega_cognition/examples/affine.json \
  --output artifacts/cognition-strict

# Propostas MCTS, falseamento, Lean e emissão nativa.
.venv/bin/python -m omega --mode bicameral cognition discover \
  omega_cognition/examples/affine.json --proposals 1 --iterations 256 \
  --wall-seconds 600 --output artifacts/cognition-bicameral

# Apenas pesquisa isolada, sem admissão, Lean, ledger ou emissão nativa.
.venv/bin/python -m omega cognition --mode dream discover \
  omega_cognition/examples/affine.json --output artifacts/cognition-dream

# Evidência empírica; ledger opcional de quatro processos locais.
.venv/bin/python -m omega cognition discover omega_cognition/examples/affine.json \
  --mode empirical --proposals 1 --bft-local \
  --output artifacts/cognition-empirical
```

O diretório de saída precisa ser novo. `creative` é um alias de `dream`.
`--guide neural` usa a pequena política opcional de `omega_synth_mcts` em CPU
(requer a dependência neural). Ela não é um modelo fundacional pré-treinado.
`--temperature` admite valores de 1 a 20. Cada ciclo tem limites explícitos de
propostas, avaliações MCTS e casos; `--cycles` admite de 1 a 16. Não existe um
loop infinito implícito. Resultados falsificados, não demonstrados e esgotamentos
são resultados de pesquisa presentes no relatório, não exceções escondidas.

## Contrato de entrada

`omega-cognitive-problem-1` define de uma a oito variáveis racionais, um oráculo
aritmético de propriedade do supervisor, exemplos de treinamento e hipóteses
opcionais. Cada domínio usa `{lower, upper, denominator}`: os testes IID sorteiam
uniformemente inteiros entre os limites e dividem pelo denominador. O contrato
formal abrange todos os racionais no intervalo fechado correspondente.

As expressões executáveis suportam constantes, variáveis, `+`, `-`, `*`, `/`,
negação e ReLU, com até 63 nós. Oráculos indefinidos invalidam a avaliação. As
obrigações Lean incluem denominadores não nulos tanto da hipótese quanto do
oráculo. Textos em `extensions` são guardados em quarentena; novas gramáticas
podem ser propostas como dados, mas não recebem automaticamente uma semântica
executável nem acesso ao compilador. O exemplo fornecido é uma tarefa sintética
com oráculo conhecido; não demonstra descoberta de uma lei da natureza.

O trabalhador recebe exemplos e a gramática, sem a fórmula do oráculo. MCTS
propõe candidatos com verificação formal desativada. Sementes fornecidas pelo
usuário também podem receber uma mutação estrutural neutra `p + 0`; esta é um
exemplo de integração, não uma melhoria de desempenho descoberta. A assinatura
comportamental em exemplos de treinamento é apenas uma heurística de novidade.
A deduplicação é estrutural, pois concordância em poucas amostras não demonstra
equivalência semântica.

## Admissão estatística sem confundir testes com prova

O ginásio executa ASTs em Ômega nativo dentro da sandbox, em lotes de até 1.024
linhas. O processo de cada lote termina e libera seu heap. Os críticos usam
extremos, pontos vizinhos, zero quando pertence ao domínio e perturbações dos
exemplos. Esses testes adversariais não contam como amostras IID. O supervisor
sorteia uma semente de validação nova depois de fixada a hipótese e a registra
para reprodução; não reutiliza a semente da geração.

Com zero falhas em `n` amostras, a cota superior unilateral de Clopper–Pearson é
`1 - alpha^(1/n)`. Para `alpha = 0.05`, cem mil amostras dão aproximadamente
`2.996e-5`: portanto **não** atendem a `p < 1e-5`. Uma hipótese fixa precisa de
pelo menos **299.572** observações sem falhas para esse critério a 95% de
confiança. Para múltiplas hipóteses, o orçamento de erro familiar é dividido por
`proposals * cycles` (Bonferroni). O tamanho padrão é o maior entre 100.000 e o
necessário para esse orçamento; o limite global de observações continua válido.

`--cases` permite experimentos menores, mas não afrouxa silenciosamente o
critério. Evidência insuficiente gera `insufficient_evidence`. Uma falha bloqueia
a admissão e registra um contraexemplo. O relatório também mostra separadamente
a cota posterior sob prior Beta(1,1); ela não substitui a cota frequentista.
As garantias estatísticas são condicionais à hipótese fixa, ao oráculo correto,
à distribuição declarada e à suposição IID. MT19937 é um gerador pseudoaleatório,
não uma fonte de observações físicas independentes. A passagem de testes não
significa generalização para outros domínios ou segurança universal.

## Cristalização e fronteiras de confiança

A ponte confiável renderiza os lemas a partir da AST validada; o trabalhador
não fornece código Lean ou táticas. `omega.certified_proof.check` executa o Lean
4 real e verifica os axiomas segundo a política existente. O sistema não adiciona
`axiom`, `sorry` ou `admit`. Uma hipótese que passa na malha finita pode falhar
na prova sobre todos os racionais do intervalo: esse caso tem teste explícito.

Após a prova, o backend existente gera e executa sob QEMU uma especialização
racional fechada RV64IM-Linux para a primeira entrada de treinamento. O resultado
é comparado exatamente com a expressão. O compilador seed usa o montador Python
no bootstrap; o binário resultante não precisa de C/GMP. Isso não constitui
uma prova de preservação do compilador inteiro, nem emissão bare-metal para
todas as construções inventadas pelo trabalhador.

`--zk-prover` e `--zk-verifier`, fornecidos juntos, habilitam uma prova real no
adaptador RISC Zero existente. Seu escopo é uma especialização RV32IM com
aritmética u32 verificada, distinta do binário RV64. Frações não integrais e
operações fora do subconjunto são recusadas. Sem um prover funcional, o relatório
não afirma `zk_verified`. Não existe recibo simulado para preencher essa lacuna.

`--bft-local` registra hashes da hipótese e da evidência num experimento com
quatro processos independentes e um nó adversarial. É o cluster de teste de
membros/chaves fixos do repositório, não autoridade BFT externa de produção.
Não publica descoberta, aciona equipamento, grava FPGA nem altera o kernel.
`kernel_activated` permanece falso; promoção exige revisão independente.

## Contenção e auditoria

`omega_agent_sandbox/jail.omega` valida as cotas; `jail.py` aplica o mecanismo
Linux existente com namespaces, seccomp, montagens explícitas e limites de CPU,
memória virtual, pilha, saída, arquivos, profundidade e combustível nativo.
Não há fallback para execução desprotegida. Trabalhadores não recebem rede,
credenciais, diretório pessoal nem montagem gravável do repositório. A versão
neural permite threads dentro do mesmo processo e bibliotecas somente leitura.
Loops Python são interrompidos por watchdog/CPU, não pelo contador de combustível
do interpretador Ômega. Os limites de memória são limites de espaço de endereços,
não uma promessa de RAM reservada por agente.

O prazo do orquestrador é conferido entre ciclos, propostas e candidatos,
e a cada lote do debate; cada subprocesso também tem seu próprio limite rígido.
Prova Lean, compilação e prova STARK usam os orçamentos existentes de suas
ferramentas. Essa sequência de ferramentas confiáveis pode prolongar o ciclo além
do prazo do orquestrador: esse prazo não é um watchdog global da sequência. Não se promete suporte a malware que explore bugs
do kernel Linux, ataques microarquiteturais ou hardware físico indisponível.

`report.json`, fontes Lean, especialização nativa e recibos contêm hashes. Os
eventos em `audit.jsonl` encadeiam o hash do evento anterior; a raiz não é assinada
externamente, portanto alteração integral pelo dono do diretório não é impedida.
O relatório distingue `formal_admission`, estado de emissão, `zk_verified` e
aprovação independente. Um status global `formal_verified` não afirma que toda
etapa posterior de emissão/prova criptográfica teve sucesso: examine os candidatos.

Testes dirigidos: `pytest testes/test_bicameral.py -q`. A suíte inclui loop
infinito, crash, bloqueio de rede/escrita, memória, 100.000 observações realmente
executadas, rejeições estatísticas/formais, cadeia Lean/RV64, ledger e CLI.

O orçamento de casos reserva cada experimento antes de iniciá-lo. Uma falha ou
timeout não devolve a reserva, pois pode ter consumido amostras. Se isso ocorrer,
`iid_accounting_complete` é falso: o contador executado inclui apenas os lotes
de experimentos concluídos, e `iid_trial_budget_reserved` limita conservadoramente
o consumo total possível.

## Cristalização completa e reverificação independente

O PR #23 já contém os modos, o ginásio e a ponte Lean/RV64. A conclusão do ciclo
agora é explícita: `formal_verified` não significa `crystallized`. O relatório
expõe `completion_target`, `configured_stages_complete`, `crystallization_complete`
e `pending_stages`. Erros posteriores à prova preservam a verdade do lema, mas
não dão sucesso à emissão, ao STARK ou à publicação do artefato.

```sh
# Prerequisitos Linux: cc, GMP/OpenSSL, QEMU RV64, bubblewrap e Rust para o prover.
bash scripts/setup-cognition.sh
bash scripts/setup-zkvm.sh

# Este exemplo não fornece candidatos: o MCTS precisa gerar a hipótese.
.venv/bin/python -m omega --mode bicameral cognition discover \
  omega_cognition/examples/seedless_affine.json \
  --proposal-source search --iterations 512 --proposals 1 --wall-seconds 900 \
  --require-seal --bft-local \
  --zk-prover build/risc0/release/omega-risc0 \
  --zk-verifier build/risc0/x86_64-unknown-linux-musl/release/omega-risc0 \
  --output artifacts/bicameral-complete

# Recria o enunciado a partir do problema esperado pelo operador; repete o
# experimento, verifica Lean, recompila o RV64 e verifica o recibo recebido.
.venv/bin/python -m omega cognition verify \
  artifacts/bicameral-complete/candidate-000/crystallization.json \
  --expected-problem omega_cognition/examples/seedless_affine.json \
  --zk-verifier build/risc0/x86_64-unknown-linux-musl/release/omega-risc0 \
  --replay-empirical
```

`--require-seal` exige os dois executáveis ZK e emissão nativa. O comando retorna
código de saída diferente de zero se não atingir a cristalização. Sem essa opção,
a exploração parcial continua disponível e o relatório declara as etapas pendentes.
`--proposal-source search` exclui sementes fornecidas; `seeds` permite depurar uma
hipótese explícita e `mixed` prioriza as propostas do MCTS antes das sementes.
Candidatos estruturalmente repetidos não consomem as vagas de avaliação de outros
candidatos do mesmo ciclo. A ordem das chaves das variáveis não altera o lema.

A publicação gera `crystallization.json`, `hypothesis.json`, o lema e recibo Lean,
a especialização e os executáveis RV64, o recibo STARK e sua identidade/journal.
Os escopos ficam fixos no formato. O verificador confere o problema esperado,
reconstrói o lema, o aceita novamente no Lean, regenera os binários em isolamento
e compara seus bytes. Ele compila independentemente a imagem RV32IM esperada e
verifica o recibo contra essa identidade e esse journal, sem executar o binário
recebido. Recalcular hashes de um recibo falso não lhe dá validade.

Os arquivos recebidos têm limites de tamanho e precisam ser regulares, sem
symlinks nos componentes internos. Sem `--replay-empirical`, as cotas declaradas
são recalculadas, mas a execução passada do ginásio não é atestada. Com a opção,
o ginásio é reexecutado com a semente registrada e o transcript é comparado.
O STARK cobre a especialização declarada, não os testes do ginásio nem todo o
compilador. Artefatos dedutivos estritos, sem etapa empírica, requerem
`--allow-deduction-only` para reverificação.

Quando `--bft-local` está habilitado, a hipótese empírica e o manifesto final
recebem registros nos experimentos BFT locais. O registro final só é produzido
após as três verificações; uma falha no registro impede o sucesso configurado.
Esses experimentos usam clusters de teste de quatro processos, com chaves fixas,
e não são um serviço BFT de produção nem uma cadeia global persistente. A
promoção do kernel continua exigindo aprovação independente.

O workflow `zkvm.yml` provisiona as versões fixadas de Lean/Mathlib, QEMU e prover
e executa o comando completo, sem sementes, com 299.572 observações, registros
BFT e reverificação com replay. Os artefatos publicados pelo CI incluem o recibo
STARK efetivo e os demais arquivos, para auditoria fora do gerador. Esse teste
não usa mocks nem recibos de desenvolvimento.
