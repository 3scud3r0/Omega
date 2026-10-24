# Estado dos três passos — Ômega 2.0

| Passo | Implementação | Evidência exigida |
|---|---|---|
| 1. Auto-hospedagem | Lexer, parser, verificação de formas, lowering, otimizador e emissor em `omega_selfhost/compiler.omega` | Bootstrap 0/1/2/3 com C idêntico e binários estabilizados idênticos; estágio 2 recompila a própria fonte com Python fora do PATH |
| 2. Backend nativo | GNU C + GMP: dialeto procedural e linguagem tensorial histórica, racionais exatos, vetores/matrizes, ReLU, AD e atualizações | Compilação/execução dos exemplos válidos; rejeição dos inválidos; comparação de IR, resultados e certificados com a referência; execução sem Python |
| 3. Núcleo verificado em Lean 4 | Semântica racional, diferenciação operacional, compilador de pilha, reduções tensoriais, produto matricial, verificação de gradientes e passos | Teoremas gerais conferidos em Lean 4.19.0/Mathlib fixado; verificador nativo independente; provas universais por coordenada das reescritas; testes adversariais |

Os passos foram implementados com os critérios de engenharia acima. O limite
formal é explícito: são provas do núcleo semântico e dos certificados, não uma
prova do GCC, da GMP, do sistema operacional ou de toda a cadeia de ferramentas.
A expressão “correção absoluta” do texto de inspiração não é uma propriedade
reivindicada por esta entrega.

## O que é auto-hospedado

O arquivo `.omega` contém o compilador real; seu runtime C fornece valores,
coleções, strings, racionais e IO. Não há uma primitiva “compile com Python”. O
estágio zero Python só compila o dialeto procedural para criar a primeira semente.
Os estágios seguintes são executáveis nativos gerados pelo próprio programa Ômega.

O compilador aceita os comandos tensoriais históricos, aliases em inglês,
provas polinomiais/tensoriais, teoremas nomeados, reescritas e políticas de passo.
Os módulos Python antigos permanecem disponíveis como APIs de referência e
compatibilidade. As rotas de evolução passam a compilar suas políticas pelo
compilador auto-hospedado. Nextorch e Orange continuam sendo aplicações Python,
conectadas à linguagem, e não fazem parte do compilador nativo.

## Escopo das provas

`omega_selfhost/TensorKernel.lean` formaliza:

- semântica exata de expressões racionais e ReLU;
- correção do valor primal do dual e igualdade entre derivação simbólica e a
  tangente dual nas direções-base;
- aceitação de gradientes para **todas** as coordenadas, sem a amostragem antiga
  acima de 64 coordenadas;
- atualização exata, preservação dos parâmetros não selecionados, taxa positiva
  e monotonicidade quando a política exige;
- semântica de reduções e produto matricial, involução da transposta;
- preservação semântica de compilação para instruções de pilha;
- identidades locais de reescrita e um verificador genérico de mínimo finito.

O verificador nativo em `formal/tensor/Main.lean` interpreta os dados da IR de forma
independente do backend C, confere formas, inicializações, valores observados,
instruções autorizadas, ruído determinístico e encadeamento de certificados.
Cada otimização ainda produz um arquivo Lean fechado com teoremas universais
`value_*` e `gradient_*`, para todas as coordenadas de todos os nós remapeados.
O Lean precisa conferir esses teoremas antes que o comando entregue a otimização.
Provas polinomiais universais também geram teoremas fechados em Lean.

As provas não usam `sorry`, `admit`, axiomas novos ou `native_decide`. O relatório
explicita `propext`, `Classical.choice` e `Quot.sound`, axiomas fundamentais usados
pelo Lean/Mathlib. ReLU em zero usa a convenção operacional de tangente zero;
não se afirma diferenciabilidade clássica nesse ponto. Divisão por zero é
recusada na admissão, embora a denotação de campo racional usada nas provas seja
total.

## Base de confiança e limites de execução

O parser/codec JSON, a tradução de dados para os objetos formais, os compiladores
C/Lean, GMP e o sistema operacional fazem parte da base de confiança. O bootstrap
convergente é um teste forte de auto-hospedagem, não uma prova contra o ataque
“trusting trust”. O programa produzido em C valida sua execução com aritmética
exata; `omega native-run` acrescenta a admissão independente pelo núcleo Lean.
A execução direta do binário C não chama automaticamente o Lean.

Não se afirma correção ou segurança de redes neurais arbitrárias, validação
causal de medições externas, generalização universal, AGI ou desempenho de GPU.
CUDA não foi validado neste ambiente. As funções históricas de síntese continuam
limitadas por seus orçamentos e universos declarados.
