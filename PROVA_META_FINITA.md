# Ômega 1.2 — demonstração de autotransformação finita e verificável

## 1. Enunciado demonstrado

Dentro da semântica racional exata implementada e do universo de programas abaixo, um processo que gera **código Ômega para uma política de busca** encontra, a partir de uma política inicial, uma política sucessora que: (i) melhora estritamente o custo total de busca em oito tarefas de treinamento; (ii) não altera o conjunto de hipóteses pesquisáveis; (iii) resolve todas as 16 tarefas booleanas; (iv) também reduz o custo agregado nas oito tarefas mantidas fora da seleção. O verificador recompõe integralmente essa afirmação, sem confiar nos custos alegados pelo sintetizador.

O adjetivo **verificável** aqui significa avaliação exaustiva de domínios finitos por dois caminhos de implementação em Python, não prova de correção de um kernel independente com Lean ou Coq.

## 2. Espaço de hipóteses e completude

Para x,y ∈ {0,1}, defina `AND(x,y)=ReLU(x+y−1)`. Considere:

`f_{a,b,c,d}(x,y) = a + b*x + c*y + d*AND(x,y)`.

Os coeficientes são inteiros no intervalo inclusivo [−2,2], portanto existem `5^4 = 625` vetores de coeficientes. Para qualquer função booleana com tabela `(t00,t01,t10,t11)` em `{0,1}^4`, escolha:

- `a = t00`
- `b = t10 − t00`
- `c = t01 − t00`
- `d = t11 − t10 − t01 + t00`

Segue por substituição nos quatro pares booleanos que `f(x,y)=txy`. Os valores de a, b e c estão em [−1,1], enquanto d está em [−2,2]. Logo a hipótese pertence ao universo permitido. **Todas as 16 tarefas são solucionáveis; a busca exaustiva não perde completude quando só altera sua ordem.**

## 3. Metalinguagem da política de busca

Uma política de busca é um programa Ômega que computa uma pontuação a partir dos quatro coeficientes candidatos. Sua semântica é:

`prioridade_w(g) = w0*(|a|+|b|+|c|+|d|) + w1*a + w2*b + w3*c + w4*d`.

Na linguagem `.omega`, o valor absoluto é expressado como `relu(z)+relu(-z)` (válido para todo racional). A busca avalia hipóteses em ordem crescente do par `(prioridade_w(g), g)`, usando a ordem lexicográfica de g para desempatar. Os cinco parâmetros w pertencem a `{−1,0,1}`, havendo exatamente `3^5=243` metaprogramas possíveis. A escolha dos sucessores é baseada exclusivamente no número de avaliações de treinamento, com desempates explícitos descritos no código `objetivo` do núcleo.

## 4. Experimento controlado e tarefas reservadas

As tabelas booleanas são identificadas por máscaras de 0 a 15. A separação é fixada pelo próprio código, antes de qualquer seleção:

`Treino = [0,1,2,4,6,7,8,13]`;
`Teste = [3,5,9,10,11,12,14,15]`.

Geração 0 só admite w=(0,0,0,0,0). A geração 1 admite qualquer w com no máximo um elemento não nulo, totalizando 11 possibilidades. A geração 2 considera todas as 243 possibilidades, incluindo as anteriores. O núcleo **reevalia todos os candidatos em cada etapa** e escolhe o minimizador determinístico do vetor de critérios `(soma de avaliações em treino, maior custo individual em treino, norma L1 da política, tupla de pesos)`.

Os resultados inteiros são:

| Geração | w escolhido | Treino (8) | Teste (8) | Total (16) |
|---|---|---:|---:|---:|
| 0 | (0,0,0,0,0) | 2902 | 3106 | 6008 |
| 1 | (1,0,0,0,0) | 617 | 648 | 1265 |
| 2 | (1,−1,0,0,0) | 481 | 437 | 918 |

A melhoria agregada no universo de 16 funções é `6008 - 918 = 5090` avaliações a menos, isto é, aproximadamente 84,72%. Nas oito tarefas de teste, a melhoria é `3106 - 437 = 2669` avaliações a menos. Esses dados demonstram transferência **entre tarefas da mesma classe finita**, e nada além disso.

## 5. Obrigações que o sistema executa

1. O núcleo `nucleo_meta.py` confirma a representação de todas as 16 funções.
2. Enumera todos os 625 candidatos e recalcula a primeira posição capaz de resolver cada função.
3. Examina 1, 11 e 243 metaprogramas nas três fases; verifica a escolha ótima de cada fase por enumeração completa.
4. Reconstrói a cadeia de evolução com referência ao registro anterior e hashes dos códigos emitidos.
5. O compilador gera IR tipada para cada código `.omega` e o verificador tradicional valida essa IR.
6. A VM executa cada código sobre os 625 candidatos, e a implementação independente confere as pontuações.
7. O teste de busca efetiva usa as prioridades da VM para ordenar os 625 candidatos e encontrar as 16 tarefas; suas contagens devem coincidir exatamente com a auditoria independente.
8. O auditor confirma a correspondência byte a byte de cada `.omega` com o certificado, a IR compilada, o código sucessor ativo e os metadados.

Essas obrigações permanecem condicionadas à correção do código Python, ao interpretador usado, às definições de domínio e às condições do ambiente. A enumeração exaustiva não prova a confiabilidade universal de um compilador, nem que a próxima arquitetura terá maior inteligência.

## 6. Proposições que continuam **não provadas**

- Evolução da inteligência geral em tarefas abertas, fora do espaço de 16 problemas;
- Transformação ou substituição independente de TODO o runtime e do compilador Ômega;
- Garantia matemática de ganhos cognitivos futuros sem limites;
- Consistência universal de sistemas lógicos autorreferentes ou fuga dos limites de Gödel;
- Compilação e verificação deste sistema pelo kernel Lean 4;
- Melhor desempenho em hardware real, outras distribuições, arquiteturas ou escalas sem novos testes.

Uma afirmação desses tipos exigiria definições formais e provas adicionais. A versão 1.2 **não** substitui tais provas por entusiasmo ou analogias.
