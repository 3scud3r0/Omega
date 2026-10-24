# OM-011 — sintaxe e semântica da Ômega

Esta especificação descreve os dois dialetos reconhecidos pelo compilador 2.0
e formaliza a execução do núcleo escalar após lowering. O arquivo executável
`omega_selfhost/OperationalSemantics.lean` define seus estados, transições,
erros e combustível. O modelo de expressões é `OmegaTensor.Expr`, em
`TensorKernel.lean`. Parsing, lowering tensorial e geração de C ainda precisam
das obrigações de refinamento das OM-026 a OM-040; esta especificação não os
considera automaticamente corretos por estarem implementados.

## Léxico e seleção de dialeto

Os fontes são UTF-8. Espaços separam tokens; `#` inicia comentário até a quebra
de linha. Números decimais finitos são exatos, sem conversão por ponto flutuante.
`1/3` é a divisão dos literais 1 e 3. Expoentes científicos não fazem parte do
léxico. Identificadores começam por letra ou `_` e continuam por letras,
dígitos ou `_`; o runtime nativo usa a classificação Unicode de `C.UTF-8`.
O prefixo `__omega_coord_` é reservado no dialeto tensorial. Strings JSON,
com escapes Unicode e sem NUL embutido, pertencem ao dialeto procedural.

O primeiro token significativo `funcao` seleciona o dialeto procedural. Caso
contrário, o parser usa o dialeto tensorial. Os dialetos não podem ser misturados
em um programa. Uma gramática válida ainda pode ser rejeitada por restrições
de tipos, nomes, dimensões, orçamento ou operações não suportadas.

## Gramática tensorial

Na EBNF abaixo, `{ x }` significa repetição e `[ x ]` significa opcional.
`nome` exclui palavras reservadas; `numero` é um decimal não negativo.
As palavras podem ser substituídas pelos aliases da tabela `ALIAS` em
`omega/sintaxe.py`, preservados no frontend nativo.

```ebnf
programa = { comando } ;
comando = declaracao | gradiente | atualizacao | prova | teorema
        | "mostrar", nome, ";" | "verificar", nome, ";"
        | "gradientes", nome, ";" ;
declaracao = ("parametro" | "perda" | "vetor" | "matriz" | "tensor" | "reescrever"),
             nome, "=", expr, ";"
           | "parametro", ("vetor" | "matriz"), nome, "=", expr, ";" ;
gradiente = "gradiente", nome, "em", nome, ";" ;
atualizacao = ("passo" | "passo_livre"), nome, "em", nome, "taxa", expr, ";"
            | "passo_ruidoso", nome, "em", nome, "taxa", expr,
              "semente", inteiro_nao_negativo, ";" ;
prova = "provar", expr, "==", expr, ";" ;
teorema = "teorema", nome, "=", expr, "==", expr, ";" ;
expr = termo, { ("+" | "-"), termo } ;
termo = unario, { ("*" | "/" | "@"), unario } ;
unario = ("+" | "-"), unario | potencia ;
potencia = atomo, [ "^", unario ] ;
atomo = numero | nome | nome, "(", [ expr, { ",", expr } ], ")"
      | "[", [ expr, { ",", expr } ], "]" | "(", expr, ")" ;
```

`^` tem precedência sobre sinal unário. Soma/subtração e os operadores de
produto são associativos à esquerda na árvore sintática; potência associa à
direita. O expoente aceito pelo núcleo tensorial é um literal inteiro em 0..20.
Listas numéricas precisam ser não vazias e retangulares, com ordem máxima 2,
dimensões 1..2048 e até um milhão de células por nó.

`+` e `-` exigem formas iguais. `*` admite pelo menos um escalar; `/` exige
denominador escalar não nulo. `@` admite matriz×vetor ou matriz×matriz com
dimensões internas iguais. `dot` exige vetores iguais, `transposta` exige
matriz, `soma` reduz a escalar e `relu` preserva a forma. `zeros` e `identidade`
recebem dimensões literais. Perdas e taxas são escalares; taxas de atualização
são positivas. O passo comum exige perda não crescente. `passo_livre` dispensa
esse teste e `passo_ruidoso` adiciona ruído exato segundo a semente registrada.
As atualizações e certificados são conferidos pelo kernel tensorial existente.

## Gramática e ordem de avaliação procedural

```ebnf
programa = { "funcao", nome, "(", [ nome, { ",", nome } ], ")", bloco } ;
bloco = "{", { instrucao }, "}" ;
instrucao = "var", nome, "=", expr_p, ";"
          | nome, "=", expr_p, ";" | expr_p, ";"
          | "retornar", expr_p, ";" | "parar", ";"
          | "se", "(", expr_p, ")", bloco, [ "senao", bloco ]
          | "enquanto", "(", expr_p, ")", bloco ;
```

`expr_p` tem, da menor à maior precedência, `||`, `&&`, `== !=`, `< <= > >=`,
`+ -`, `* / %`, unários `! -`, átomos e indexação `expr_p[expr_p]`.
Átomos são números, strings, nomes, chamadas, listas e parênteses. Os operadores
binários associam à esquerda. `^` e `@` não pertencem ao dialeto procedural.

Argumentos de chamadas, listas e operadores comuns são avaliados da esquerda
para a direita. `&&` e `||` fazem curto-circuito e retornam racional 0 ou 1.
Zero é falso; strings/listas/objetos vazios são falsos. As demais instâncias
são verdadeiras. Listas e objetos são referências mutáveis. `%` exige inteiros
e segue o resto C com sinal do dividendo. Índices são inteiros não negativos
e precisam estar no intervalo; strings são indexadas por bytes UTF-8.
Uma função sem `retornar` produz 0; `principal` é o ponto de entrada. Funções,
escopos, tipos de chamadas e nomes do dialeto procedural ainda recebem parte
de seus diagnósticos do C gerado. O modelo formal abaixo cobre o núcleo
numérico, não a memória mutável, os builtins de I/O ou todo esse dialeto.

## Máquina formal do núcleo

Um estado é `⟨code, stack⟩`, onde `code : List Instruction` e `stack : List ℚ`.
O ambiente `s : Nat → ℚ` associa coordenadas já resolvidas a valores racionais.
Os identificadores desconhecidos devem ser recusados antes de construir esse
ambiente; a função formal é total e não implementa resolução de nomes.

`push q` empilha q; `load i` empilha `s i`. Os operadores consomem operandos
do topo: com stack `b :: a :: xs`, `add` produz `(a+b) :: xs`, `mul` produz
`(a*b) :: xs`, e `div` produz `(a/b) :: xs` somente se `b ≠ 0`.
`neg`, `pow n` e `relu` consomem um elemento. ReLU produz `max 0 a`.
`gate`, usado pelo lowering de derivadas, consome `b :: a :: xs` e produz b
se `a > 0`, ou 0 caso contrário. A convenção de derivação em ReLU(0) é 0.

Cada transição consome exatamente uma instrução. `Step.instruction` só existe
quando `checkedInstruction` retorna sucesso. Código vazio é terminal, sem
consumir combustível. Código não vazio com combustível zero produz
`fuelExhausted`; stack insuficiente produz `stackUnderflow`; divisão com dois
operandos e denominador zero produz `divisionByZero`. Nenhum erro produz um
valor numérico sentinela. Combustível de instruções não mede custo aritmético.

Teoremas fechados: `step_deterministic` prova unicidade do próximo estado;
`checked_instruction_agrees` vincula instruções aceitas ao modelo anterior;
`run_agrees` prova que toda execução aceita termina com código vazio e concorda
com `OmegaTensor.execute`. O teorema `OmegaTensor.compile_sound` existente
vincula a compilação da AST à avaliação matemática; `compiled_checked_result`
faz essa ligação para toda execução aceita pela máquina com erros explícitos.
A execução matemática
total usa a divisão de ℚ; a máquina operacional recusa divisão por zero.
Consequentemente, correspondência de uma execução aceita não é uma autorização
para aceitar expressões indefinidas.

`testes/lean/OperationalExamples.lean` exercita valores, ordem da stack,
divisão por zero, underflow, parada e orçamento, conferidos pelo Lean.
