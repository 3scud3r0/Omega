# Tensores nativos e admissão formal

`omega native-build` chama o compilador `.omega` nativo e o compilador C. O grafo
é emitido como código por operação; a execução não carrega uma VM Python nem
interpreta a fonte Ômega. O runtime usa GMP para racionais, não floats.

São suportados escalares, vetores e matrizes de ordem até dois, listas,
`zeros`, `identidade`, `+`, `-`, multiplicação escalar, divisão escalar, potência
inteira 0..20, `@`, `dot`, `transposta`, `soma`, ReLU, gradientes e as três
políticas de atualização. A política ruidosa reproduz a sequência MT19937 e a
amostragem de `random.Random(seed).randrange(-1,2)` do motor histórico.

## Execução verificada

```sh
.venv/bin/python -m omega native-build exemplos/rede_profunda.omega \
  --saida artifacts/nativo/rede
.venv/bin/python -m omega native-run artifacts/nativo/rede \
  --saida artifacts/nativo/rede-result.json
.venv/bin/python -m omega verify-native artifacts/nativo/rede-result.json
```

O resultado inclui IR, estado inicial, estado final, valores dos símbolos e
certificados. O verificador Lean, compilado em executável independente, confere:

1. Tipagem por formas, referências anteriores e assinatura dos parâmetros.
2. Igualdade das inicializações com as expressões do programa.
3. Valores numéricos observados e ausência de divisões por zero.
4. Gradientes exatos em todas as direções-base, sem limiar de amostragem.
5. Autorização da instrução, taxa, semente, atualização e monotonicidade exigida.
6. Ordem dos certificados, continuidade dos estados e estado final.

Ausência, timeout ou rejeição do Lean impede a publicação do resultado pelo
comando de execução verificada. O binário C também pode ser executado diretamente
para produzir os dados; isso não substitui a verificação independente do Lean.

## Reescritas e identidades universais

O otimizador está no próprio compilador `.omega`. Ele elimina zeros/unidades,
duplas negações, duplas transpostas e ReLU repetida, preservando as formas.
`native-build --optimize` confere a testemunha estrutural em Lean e gera teoremas
universais para os valores e gradientes de cada coordenada de cada nó remapeado.
Os arquivos `.opt.lean` podem ser conferidos novamente no projeto `formal/tensor`.
Otimizações sem prova aceita são recusadas; não se enfraquecem asserções.

`provar`, `teorema` e `verificar` aceitam identidades polinomiais e tensoriais.
O runtime faz a normalização algébrica exata e o comando verificado gera provas
fechadas em Lean para todas as coordenadas. Strings vindas do programa não viram
código Lean: somente os construtores de expressão e os racionais validados são
renderizados pelo gerador de provas.

## Reprodução das ferramentas formais

Lean está fixado em 4.19.0; Mathlib no commit
`c44e0c8ee63ca166450922a373c7409c5d26b00b`. `scripts/setup-native.sh` usa o manifesto
Lake fixado e compila as dependências das fontes. Não depende do cache externo de
Mathlib nem desativa TLS, assinaturas ou checksums. O Lean oficial conserva a
verificação SHA256 do instalador anterior.

O parser/codec e a ligação com GMP/C pertencem à base de confiança. A cobertura
matemática e suas condições estão em `ESTADO_DOS_TRES_PASSOS.md`.

O wheel inclui o compilador, seus headers e o núcleo lógico. O projeto formal e
o SDK nativo são preparados pelo pacote fonte e pelo script de instalação.
Em uma instalação isolada do wheel, configure `OMEGA_TENSOR_KERNEL` com o
executável preparado, `OMEGA_TENSOR_PROJECT` com o projeto `formal/tensor` e
`OMEGA_LAKE` com o Lake instalado para conferir provas fechadas.
