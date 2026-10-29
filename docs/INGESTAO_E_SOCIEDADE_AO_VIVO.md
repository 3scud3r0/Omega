# Ingestão semântica, sociedade e acompanhamento ao vivo

Esta implementação adiciona os 53 caminhos nomeados no pedido e três módulos de acompanhamento, totalizando 56. O manifesto completo é `roadmap/semantic-society-files.json`. Existem ainda adaptadores Python/C, um entry point nativo e testes de integração. Os algoritmos de domínio são `.omega`; transporte HTTP, armazenamento transacional, parsing de linguagens e coordenação de processos são interfaces de host explícitas.

## Arquivos

- `omega_ingest/`: levantamento WASM inteiro, AST escalar C/Python, normalização ONNX e inferência de contratos por intervalos.
- `std/math/`: intervalos transcendentais, Newton, LU com pivoteamento, inversão racional, valores singulares para matrizes de duas colunas, exponencial matricial com resto e ODE linear.
- `hardware/cuda_native/`: ABI C para os kernels existentes, avaliação por warp, GEMM racional SIMT com erros de overflow e multiplicação inteira larga.
- `civilizacao_agentes/`: votos assinados, quóruns, leilão com escrow declarado, interseção de metas, DAG de conhecimento e contrato social.
- `incubadora_continua/`: conjecturas, profiler agregado, propostas de síntese, estresse limitado a 10.000 casos e diário nativo.
- `sociedade_hierarquica/`: DAG de tarefas formais, síntese de nós, contraexemplos, juiz com autoridade de prova e barramento de handles.
- `metamorfose_cognitiva/`: admissão de refatoração, dicionários de tokens, linhagens e deduplicação de lemas autenticados. Descobertas não se tornam novos axiomas confiáveis.
- `fabrica_descobertas/`: famílias de conjecturas, candidatos a invariantes, comparação de modelos de custo e simulações racionais.
- `imunologia_sistemica/`: elegibilidade por utilidade, constituição fixada por hash, quarentena com permissões por estágio e auditoria de planos explícitos.
- `infraestrutura_soberana/`: round robin de trabalho finito, árvores Merkle com provas de inclusão, frames P2P assinados e emissão de controlador C freestanding.
- `tools/dashboard/`: TUI, controle de fitness, depurador racional, descrição de rotas, manifesto DAG, log encadeado e redutor de controles.
- `formal/Universal/`: núcleo intrinsecamente tipado, limite de Taylor menor que `10^-9` no domínio declarado, preservação do fragmento aritmético e segurança do modelo finito de arena.

## Rastreador real e histórico

```sh
# Cria uma execução persistente; copie o id retornado.
.venv/bin/python -m omega live --state build/live create exemplos/nativo/spec.json --iterations 128
# Em outro terminal, inicie o executor com o mesmo id.
.venv/bin/python -m omega live --state build/live work ID
# A interface mostra o endereço e um token local gerado para esta sessão.
.venv/bin/python -m omega live --state build/live monitor --port 8765
# Alternativa no terminal:
.venv/bin/python -m omega live --state build/live tui ID --watch
.venv/bin/python -m omega live --state build/live history --run ID --follow
```

O monitor é um servidor de loopback, sem serviço persistente instalado. O usuário abre o endereço impresso e fornece o token no campo da página. Dados e controles exigem Bearer; o token não fica em query strings. HTTP fornece snapshots e comandos, SSE permite retomar eventos por cursor e `/api/ws` fornece eventos para clientes WebSocket autenticados. Controles WebSocket de escrita não são aceitos; escritas usam REST com revisão.

É possível pausar, retomar, executar passos, cancelar, ajustar os quatro objetivos de fitness e mudar o orçamento de iterações. A página diferencia revisão solicitada e revisão aplicada. Comandos concorrentes recebem conflito 409; é necessário atualizar a revisão. Uma prova já em andamento termina no seu checkpoint seguro, e um cancelamento impede a admissão posterior do resultado. A interface não permite trocar chaves, constituição, provador ou fonte executável.

```sh
.venv/bin/python -m omega live --state build/live control ID pause --revision 0
.venv/bin/python -m omega live --state build/live control ID step --revision 1 --value 1
.venv/bin/python -m omega live --state build/live control ID weights --revision 2 --value '["1/5","4/5","0","0"]'
.venv/bin/python -m omega live --state build/live audit
.venv/bin/python -m omega live --state build/live export build/history-export.jsonl
```

O histórico usa SQLite WAL com transações e sincronização completa. Cada evento contém sequência, execução, ator, relógio, payload, hash anterior e hash SHA-256. Reiniciar a interface não apaga eventos. `audit --head HASH` verifica uma âncora externa; o dono de todo o banco e de todas as âncoras continua sendo uma hipótese de confiança. Exportações preservam todos os eventos, além das últimas 500 linhas exibidas no navegador. Seeds de assinatura não entram nos eventos.

O executor nativo salva seu estado de busca entre passos, aplica controles nos checkpoints, emite os candidatos e só marca admissão formal depois de Lean. O modo `--no-proof` é explicitamente uma busca sem admissão. Um trabalhador detém lease exclusivo; um segundo não pode tomar uma execução ativa. Uma execução pausada pode estacionar após timeout e ser retomada por outro processo. O backend CUDA deve ser escolhido explicitamente e precisa de caixas de entrada/saída; ausência de GPU é um erro registrado, sem substituição silenciosa por CPU.

## Ingestão

```sh
.venv/bin/python -m omega ingest python arquivo.py --function calcular --output build/lift-python
.venv/bin/python -m omega ingest c arquivo.c --function calcular --output build/lift-c
.venv/bin/python -m omega ingest wasm modulo.wasm --function calcular --output build/lift-wasm
.venv/bin/python -m omega ingest onnx modelo.onnx --output build/lift-onnx
.venv/bin/python -m omega ingest safetensors pesos.safetensors
```

- Python admite funções matemáticas sem efeitos, atribuições locais e retorno escalar. O padrão preserva operações inteiras; floats e divisão real exigem `--rational-reals`, que declara a mudança de modelo. Nenhum módulo estrangeiro é importado ou executado.
- C usa `pycparser`, rejeita preprocessamento não suportado, ponteiros, chamadas, efeitos e controle de fluxo fora do fragmento. Inteiros signed de 32 bits têm overflow e divisão inválida rejeitados; unsigned usam redução modular. Isso preserva comportamento definido no fragmento, sem atribuir comportamento a UB de C. Não é um conversor completo de SQLite/libpng.
- WASM é validado como binário, e o levantador nativo lê seções e LEB128. O fragmento admite i32/i64, constantes, locais, drop e adição/subtração/multiplicação com wrap. Emite valores SSA em bloco único. Imports, memória, SIMD, floats, calls e branches ainda são rejeitados. A segurança não é obtida removendo silenciosamente essas operações.
- ONNX lê protobuf sem pickle nem arquivos externos, exige dimensões estáticas e suporta operações afins, Gemm/MatMul, ReLU, aritmética, transpose e reshape; primitivas decompondo atenção são admitidas dentro dos limites do grafo. Exp/Sqrt/Softmax requerem `--allow-approx` e posterior contrato de erro/domínio. Pesos finitos viram os racionais exatos de seus bits; a inferência não reproduz necessariamente cada arredondamento IEEE da implementação original. O parser não requer PyTorch.
- SafeTensors contém pesos, não arquitetura. O leitor valida offsets, dtype, tamanho e sobreposição e retorna pesos exatos; uma arquitetura explícita continua necessária para transformá-los em um modelo executável.

`formal_admission=false` é mantido nos levantamentos até uma prova independente do contrato adequado. Um relatório de parser, teste amostral ou filtro de intervalos não é um certificado universal do binário estrangeiro. O teorema `LifterEquivalence` cobre o modelo aritmético declarado, não toda semântica C/WASM e toolchain.

## Garantias delimitadas

Uma SVD genérica não tem fatores racionais exatos; o adaptador retorna intervalos de valores singulares para duas colunas. Exponencial matricial e Euler linear retornam cotas analíticas e resíduos exatos; a presença de uma cota numérica não substitui uma prova formal completa desse algoritmo. Conjecturas e invariantes encontrados em amostras permanecem candidatos. Medições de custo não provam melhora assintótica universal.

O quórum é `n-floor((n-1)/3)`, suficiente para interseção honesta sob o limite de falhas declarado, com identidades e assinaturas fixadas. A rotina valida certificados; liveness de uma rede arbitrária e um protocolo BFT completo contra escalonadores assíncronos não são teoremas deste módulo. Leilões e ações usam recursos modelados; não movimentam dinheiro nem controlam equipamento físico por conta própria.

A arena, o barramento e o firmware têm domínios explícitos. `SharedRing` fornece payload compartilhado para processos cooperantes criados por fork, sem serialização no acesso emprestado; empréstimos não devem sobreviver ao contexto. Não há promessa de latência zero. O firmware emitido é um controlador inteiro limitado sem heap, não uma imagem de SO contendo todo o enxame, GMP e Lean.

Os kernels GPU usam inteiros SIMT. Tensor Cores de ponto flutuante não executam multiplicação racional arbitrária exata nativamente. Metas como “1M nós/s” dependem de medição física; não são anunciadas como resultado sem GPU. A constituição protege o modelo de ações e os caminhos de código fixados; não prova alinhamento de qualquer AGI ou segurança de propriedades físicas que não foram especificadas.
