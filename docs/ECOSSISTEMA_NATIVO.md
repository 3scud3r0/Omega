# Biblioteca nativa e incubação automática

O núcleo dos algoritmos abaixo é `.omega`, compilado pelo compilador auto-hospedado para C/GMP. Python coordena ferramentas, emissão de provas e supervisão. O acesso ao sistema e a criptografia usam uma interface C explícita com POSIX e OpenSSL; não há implementação caseira de SHA-256 ou Ed25519.

## Arquivos e responsabilidades

| Arquivo | Implementação |
| --- | --- |
| `std/math.omega` | Newton racional para raiz; Taylor com resto para exponencial; redução de escala e série de log; seno/cosseno com pequeno ângulo e duplicação. Retorna intervalos com arredondamento externo. |
| `std/string.omega` | Buffers, divisão/substituição, formatação `p/q`, codec documental canônico com tags e chaves ordenadas. |
| `std/io.omega` | Arquivos e JSON nativos, caminhos relativos a uma raiz, substituição atômica, append com comparação de hash. |
| `std/collections.omega` | Heap estável, tabela hash com sondagem linear e tombstones, grafo dirigido em matriz. Capacidades explícitas. |
| `std/ast.omega` | AST escalar topológica: constantes, entradas, quatro operações, negação e ReLU; avaliação com erros de domínio e orçamento de bits. |
| `std/proof.omega` | Verificação da assinatura de uma autoridade fixada, finalidade, sujeito, política e expiração de permissões. |
| `runtime/memory_arena.omega` | Planejamento de regiões com donos, gerações, empréstimos e liberação LIFO. |
| `runtime/static_arena.h` | Arena de payload em armazenamento fornecido pelo chamador; sem malloc; verifica limites e validade dos handles. |
| `banco_de_dados.omega` | Log documental append-only, hashes encadeados, auditoria contra uma cabeça confiável, inserção com permissão e CAS sob flock. |
| `synthesis.omega` | MCTS nativo sobre prefixos de uma gramática; seleção racional, expansão, rollout, avaliação, backprop e emissão de programa `.omega`. |
| `fitness.omega` | Média harmônica com barreira, BWT, custo de AST, estabilidade e objetivos de velocidade/memória; benchmark em um único processo nativo. |
| `civilizacao_agentes.omega` | Assinatura Ed25519 do remetente, permissão independente do contrato, escopo do destinatário/canal e rejeição persistente de nonces repetidos. |
| `incubadora_continua.omega` | Proposta com ganhos medidos e custo estrutural; aprovação manual ou automática; assinatura de autorização local. |
| `ginasio.omega` | Simulações racionais de controle e mercado; MCTS interativo com recarga dos pesos; eventos e programa vencedor. |
| `tools/repl.omega` | REPL aritmético nativo com variáveis, precedência, parênteses, mensagens de erro e continuidade após uma linha inválida. |
| `tools/package_manager.omega` | Verificador offline de versões, DAG de dependências, arquivos SHA-256 e lock com permissão formal. |
| `tools/native_suite.omega` | Aplicação nativa que expõe os módulos para CLI, testes e supervisão. |
| `omega_selfhost/native_std.h` | Intrínsecos POSIX, GMP, relógio, entrada de linhas, SHA-256, Ed25519 e escrita confinada. |
| `omega_native/` | Link/build, codec, autoridade de provas, clientes, MCTS→Lean, provas analíticas, supervisor e CLI. |
| `formal/Native/` | Preservação do prefixo em append, contagem, contratos de chave/arena, Lyapunov do controle e limites analíticos reais. |

## Uso

Pré-requisitos para provas e automutação: checkout do repositório, GCC, desenvolvimento de GMP e OpenSSL (`libgmp-dev`, `libssl-dev`), Python com `requirements/cpu-py312.lock`, Lean/Mathlib fixados pelo setup e Bubblewrap. O wheel inclui os fontes `.omega` usados pela biblioteca nativa e pelo REPL; `math` e as operações locais podem compilar a partir desse pacote. Lean e a publicação do compilador continuam exigindo o checkout com a toolchain formal preparada. O cache de binários é invalidado pelo código vinculado e pelos headers do runtime. Os módulos da suite usam vinculação dinâmica com checagens de tags nativas; esse modo está registrado no manifesto, sem atribuir a eles a inferência estática limitada da linguagem procedural.

```sh
bash scripts/setup-native.sh
.venv/bin/python -m omega native build
.venv/bin/python -m omega native repl
.venv/bin/python -m omega native math exp 1/3 --bits 32
.venv/bin/python -m omega native math sqrt 2 --bits 32 --proof-output build/sqrt-proof
.venv/bin/python -m omega native keygen build/native-authority.seed
```

O REPL aceita `let a = 15/2;`, `let b = 8/3;` e `mostrar a*b;`, imprimindo `20/1`. Não compila comandos arbitrários digitados como ações externas. `sair` e EOF encerram o processo.

O CLI também oferece `db-put`, `db-get`, `db-audit`, `search`, `fitness`, `simulate`, `package-check`, `gym`, `nursery` e `incubate`; consulte `omega native <comando> --help`. Os documentos JSON de entrada aceitam inteiros, strings, arrays e objetos. No cliente Python, use `Fraction` para números não inteiros; o codec preserva a diferença entre a string `"1/3"` e o número racional `Fraction(1,3)`. O JSON nativo não inclui booleanos, null ou bytes NUL.

```python
from fractions import Fraction
from pathlib import Path
from omega_native.authority import Authority, create_key, GENESIS
from omega_native.api import insert, lookup
root = Path('build/memory').resolve()
root.mkdir(parents=True, exist_ok=True)
authority = Authority(create_key(root/'issuer.seed'))
document, permit = authority.database(
    key='control', document={'aileron': Fraction(7, 3)},
    head=GENESIS, policy='flight-v1', bounds={'aileron': ['-30', '30']},
    directory=root/'insert-proof')
written = insert(root, 'memory.log', GENESIS, 'control', document,
                 authority=authority.public, permit=permit, policy='flight-v1')
assert lookup(root, 'memory.log', written['head'], 'control')['aileron'] == Fraction(7, 3)
```

Guarde `written['head']` em um canal externo confiável. Uma cadeia SHA-256 detecta alterações relativas à cabeça fixada; ela não impede o dono do disco de substituir tanto o histórico quanto a âncora. Truncamentos e linhas não canônicas são rejeitados. Não há reparo silencioso de um append interrompido.

## Aprovação automática

`omega native incubate` e `omega native nursery` usam `--approval-mode auto` por padrão. `--auto-approve` é um alias explícito. Nenhum prompt ou token humano é solicitado nesse modo. A assinatura local é emitida pelo supervisor com uma chave de serviço, criada com modo 0600; ela é distinta da chave do agente e da autoridade Lean. O modo manual continua disponível com `--approval-mode manual`.

```sh
.venv/bin/python -m omega native incubate '(x*2)-x' \
  --receipt build/elite/certificate.json --proof-directory build/elite \
  --key build/native-authority.seed --output build/incubation-001 \
  --auto-approve --stage-only

# Epochs nativos apenas quando a máquina estiver ociosa; termina após um ciclo.
.venv/bin/python -m omega native nursery --output build/nursery --cycles 1 --auto-approve
```

A primeira execução precisa de um receipt Tier-2 emitido pela autoridade configurada, como o produzido por `omega native search`. A proposta só avança após reconstrução independente da equivalência, redução de nós e ganho de tempo observado em ensaios nativos alternados. A mediana é medida novamente antes da adoção. A prova não certifica um ganho universal de throughput do hardware.

Sem `--stage-only`, `incubate` instala a geração após o bootstrap de quatro estágios e a estabilização dos hashes. `--commit` também substitui o fonte e cria o commit; requer árvore e índice limpos. Alterações do usuário ou mudança do hash base durante o ciclo abortam a adoção. Assinaturas, finalidade, política, validade e artefatos continuam obrigatórios no modo automático. A autorização é consumida uma única vez; uma falha exige nova proposta.

`nursery --forever` mantém o supervisor até interrupção. `--evolve --install` habilita adoção de identidades do catálogo de mutações; `--commit` habilita publicação Git. O supervisor gera desafios limitados de controle, polinômios e diofantinas, sintetiza em `.omega`, solicita Lean e encaminha apenas resultados admitidos ao banco de abstrações existente. Não é instalado nenhum serviço do sistema automaticamente.

## Contratos e limites

- A autoridade reconstrói obrigações numéricas a partir da política confiável, roda Lean, verifica dependências e compila o `.olean`. O código nativo verifica a atestação assinada dessa autoridade. Uma chave de agente sozinha não pode autorizar uma proposição. O kernel Lean completo não é embarcado nos pequenos verificadores C.
- `math --proof-output` gera uma prova sobre os extremos realmente retornados pelo programa nativo. Exponencial, logaritmo, seno e cosseno são aproximações com intervalos, não valores racionais exatos das funções reais. Os domínios e orçamentos são explícitos no código.
- O MCTS limita nós, exemplos, capacidade e iterações. Soluções que passam nos exemplos continuam com `formal_admission=0` até a prova universal independente. A autossíntese de políticas é uma busca na gramática escalar; não é síntese irrestrita do próprio motor Turing completo nem prova de minimalidade global.
- A arena C administra payload estático sem heap. O runtime geral e GMP/OpenSSL alocam memória. Os handles têm verificação dinâmica de dono/geração; não há aqui um sistema completo de tipos lineares que demonstre ausência de vazamentos para qualquer programa compilável.
- O ginásio usa o MCTS nativo em CPU, mostra eventos JSON e recarrega o arquivo de objetivos entre iterações. Tempo é medido; `nodes*64` é um modelo de custo de memória, não RSS real. Os modelos de pêndulo e braço são discretizações declaradas, não certificados de uma planta física. O backend CUDA já existente permanece em `omega hyper`; não se declara uma medição de GPU onde não há dispositivo.
- O gerenciador verifica um conjunto offline de arquivos e dependências fixadas; não baixa pacotes nem executa scripts de instalação. A segurança de SHA-256/Ed25519 e a correspondência entre sistema físico e especificação são hipóteses externas, não teoremas de inviolabilidade absoluta.

## Exercícios reproduzíveis

```sh
.venv/bin/python -m omega native search exemplos/nativo/spec.json \
  --key build/native-authority.seed --output build/native-search-001 --iterations 128
.venv/bin/python -m omega native fitness exemplos/nativo/fitness.json
.venv/bin/python -m omega native gym exemplos/nativo/gym.json
```

Durante `gym`, editar `exemplos/nativo/weights.json` altera os objetivos no próximo passo e reinicia as estatísticas de valor da árvore. O arquivo final permanece sem admissão formal até ser submetido ao fluxo `search`/Tier-2. Cada rodada é limitada; não há promessa de sintetizar uma solução para qualquer contrato.
