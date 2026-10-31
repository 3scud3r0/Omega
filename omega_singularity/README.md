# Seis componentes em `omega_singularity.omega`

Distribuição determinística de fontes com prefixo Ômega executável e seções
C/Python/WGSL inertes, extraíveis por hash. Os seis módulos pedidos são
implementações canônicas; o gerador resolve seus imports e os reúne no arquivo
único. Dependências e módulos originais ficam declarados no manifesto, sem
preenchimento artificial nem contagem de linhas como evidência de capacidade.

## O que foi implementado

| Componente | Implementação e limite |
| --- | --- |
| `solomonoff_induction.omega` | Busca bottom-up com beam, descrição prefixada e mistura finita de programas polinomiais visitados. Até 1.024 nós, quatro variáveis e nove nós de AST expandida por candidato. Não calcula Solomonoff universal ou complexidade mínima de Kolmogorov. |
| `godel_recursive_improver.omega` | Reescritas totais em racionais, normalização polinomial, histórico e redução estrita do custo de nós aritméticos. Gera propostas; não prova aumento de inteligência. |
| `synthetic_universe_generator.omega` | Tarefas afins, polinomiais e um passo conservativo discreto, com seed e partições separadas. Gabaritos produzem obrigações verificáveis no kernel; não são fatos físicos medidos. |
| `symbolic_neuro_dag.omega` | Hash-consing, validação topológica, avaliação exata, formas polinomiais e custo. Uma política linear exata de seis pesos aprende preferências de opcode; serve apenas como conselho. Não equivale a uma rede de linguagem treinada. |
| `decentralized_epistemic_swarm.omega` | Quarentena, deduplicação por conteúdo, contraexemplos e limites. O adaptador P2P autentica Ed25519 e revalida certificados localmente; não aceita votos como provas. |
| `parallel_induction_substrate.omega` | Oráculo CPU e contrato de buffers para shader WebGPU/WGSL. Uma invocação por programa, até 256 programas de 32 nós. A GPU é uma peneira, seguida de avaliação e verificação na CPU. |

A gramática compartilhada tem `const`, `var`, `neg`, `add`, `sub` e `mul`.
Entradas e intermediários CPU são racionais exatos, com teto de 256 bits para a
avaliação. Os certificados do kernel usam o domínio racional finito descrito em
`kernel/README.md`. Exaustão não autoriza uma proposta.

## Indução e política

Observações têm formato `[[entradas], saída]`. Treino: 1..32 exemplos; holdout:
1..32 exemplos com entradas diferentes do treino. O holdout é avaliado depois
da escolha e não participa da pontuação. Queries são limitadas a 16.

A descrição é uma árvore prefixada: opcode de três bits; variável com mais dois
bits; constante com sinal e Elias-gamma para `abs(n)+1` e denominador; operadores
recursivos. A mistura usa `2^-bits` sobre representantes polinomiais visitados
compatíveis com o treino, não sobre todos os programas possíveis. Deduplicação
usa coeficientes, nunca apenas respostas observadas. Faixas de previsão expõem
discordância; não há garantia de generalização. `budget_exhausted` e
`beam_pruned` indicam cortes. Não se afirma ótimo universal.

`opcode_prior` permite ordenar add/sub/mul por preferências externas. O modo
`policy-update` do DAG atualiza seis pesos limitados por feedback explícito.
Esse feedback não concede autoridade de prova, aprovação ou promoção.

`self-play` conecta os seis módulos: gera tarefas, entrega ao aprendiz somente
observações (sem gabarito), filtra candidatos, verifica certificados, propõe
reduções, prepara fatos para a quarentena e atualiza preferências locais.
São até quatro rodadas de quatro tarefas; falhas ficam registradas como
abstenções. Não há conexão externa ou ativação estável automática nesse comando.
Esse holdout fornece feedback de validação ao ciclo; uma avaliação científica
independente exige outras seeds e tarefas que não participem desse feedback.

## Ciclo de propostas

`cycle` lê hashes do compilador e dos componentes existentes sem alterá-los.
Propõe reescritas de um DAG, reconstitui o certificado em uma implementação
Python independente, chama o verificador nativo C, confere observações e
compila baseline/candidato para ELF. Ambos executam no sandbox, com resultados
comparados. Até oito gerações; ausência de ganho estrito interrompe o ciclo.

O certificado formal verifica **igualdades fechadas dos coeficientes** e uma
igualdade de naturais com testemunha positiva para a redução de custo. A
reflexão de programas em polinômios continua parte da base confiável; não se
afirma um teorema geral de refinamento desse refletor, do C ou do hardware.
Também não se prova ganho em inteligência, energia ou tempo de parede.

A fronteira local de busca avança em memória. O código instalado, o compilador,
o kernel e o processo atual não são sobrescritos. Ativação estável é uma API
separada que delega ao `Versions` existente e exige decisões autenticadas dos
papéis independentes de verificador e promotor. Um booleano do proponente não
serve como autorização. A exportação gera proposta revisável, sem aplicá-la.

## P2P

Não há conexão ou listener no import. O comando `serve` é explícito, usa
loopback por padrão e exige allowlist de chaves públicas. Cada conexão contém
um frame de até 64 KiB, com timeout e uma mensagem Ed25519 com TTL de no máximo
uma hora. Há sequência monotônica persistente por peer, expiração, deduplicação
por certificado e quotas transacionais SQLite. Há até oito conexões simultâneas
e 32 mensagens autenticadas por peer/minuto. A assinatura autentica a origem;
a admissão depende do kernel local e permanece restrita ao escopo do certificado.
Certificados e DAGs são dados; não viram comandos ou arquivos executados.

O transporte implementado é TCP enquadrado com autenticação de mensagens,
sem descoberta pública, consenso global, NAT traversal ou confidencialidade TLS.
Nenhum peer externo é contatado pelos testes. Provas válidas não demonstram
automaticamente utilidade, novidade ou qualidade de uma descoberta.

## WebGPU

Shader WGSL fixo, compilado por wgpu-native para o backend disponível, como
Vulkan ou Metal. O domínio usa racionais reduzidos com `abs(n) <= 32767` e
`1 <= d <= 32767`. Cancelamento e MDC mantêm produtos/somas intermediários
dentro de i32; resultados maiores são recusados explicitamente. Não representa
aritmética racional ilimitada na GPU. Programas maiores continuam na CPU.

O adaptador roda como ferramenta confiável em processo com quotas de tempo,
CPU, memória e saída. Os programas candidatos são dados para o shader fixo.
O limite virtual do processo de driver é 4 GiB e arquivos/memfd têm teto de
512 MiB; isso não mede RAM física ou memória de vídeo consumidas.
Nenhum acesso de dispositivo é acrescentado ao sandbox de execução de candidatos.
Resultados da GPU sempre voltam à avaliação exata CPU e ao kernel. `cpu` é o
backend de referência. No caminho GPU, a CPU primeiro empacota os grafos sem
executá-los sobre as observações; somente os sobreviventes selecionados voltam
para avaliação CPU e certificados. A admissão verifica até 16 observações e,
por padrão, no máximo oito sobreviventes; cortes são declarados no resultado.
O modo CPU também limita a quantidade de certificados produzidos. `cpu` é o
padrão; `auto` declara fallback; `gpu` falha explicitamente se indisponível.
Não há promessa de milhões de hipóteses por segundo, memória/energia constantes
ou equivalência de drivers sem medições. Adaptadores de software são identificados
e não contam como evidência de execução em GPU física.

## Comandos

```sh
python -m omega_recursive run universe omega_singularity/examples/universe.json
python -m omega_recursive prove-universe omega_singularity/examples/universe.json
python -m omega_recursive self-play omega_singularity/examples/self-play.json
python -m omega_recursive run induce omega_singularity/examples/induction.json
python -m omega_recursive cycle omega_singularity/examples/cycle.json
python -m omega_recursive cycle omega_singularity/examples/cycle.json --export /tmp/omega-proposal
python -m omega_recursive sieve omega_singularity/examples/sieve.json --backend cpu
python -m omega_recursive inspect omega_singularity.omega
python -m omega_recursive extract omega_singularity.omega /tmp/omega-recursive-sources
python -m omega_recursive.amalgamation --check
python -m pytest testes/recursive -q
```

Também disponível como `omega recursive ...`. Prérequisitos: instalação Ômega,
com host Linux x86-64 para o sandbox atualmente implementado. O backend Metal
e a execução integral em Apple Silicon não foram validados nem portados aqui.
GMP/OpenSSL de desenvolvimento, compilador C e Bubblewrap configurado. O kernel
C e os executáveis ELF emitidos não precisam de Lean. O bootstrap/adaptador
Python continua sendo uma dependência das ferramentas de build/orquestração.
O grande arquivo usa o mesmo formato de contêiner do kernel anterior; o frontend
genérico de módulos não deve receber o arquivo misto inteiro com seus comentários.

Opcional GPU: `pip install '.[webgpu]'`. P2P autenticado: `.[tools]` para
cryptography. Instalar drivers ou iniciar a rede não faz parte do import ou dos
comandos CPU. Resultados executados e pendências ficam em `VALIDACAO.md`.
