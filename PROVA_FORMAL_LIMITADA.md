# Prova de evolução e de correção dentro de um domínio finito

## Definições

- Domínio `D = {0,1} × {0,1}`; cardinalidade `|D| = 4`.
- Alvo `T(x,y)=x XOR y`.
- Hipóteses `H_r = {f_abc : (a,b,c)∈ℤ³, |a|,|b|,|c|≤r}`.
- Função `f_abc(x,y)=a R(x+y)+b R(x+y-1)+c R(x+y-2)`, `R(z)=max(0,z)`.
- Perda `E(f)=Σ_(x,y)∈D(f(x,y)-T(x,y))²`.
- Custo secundário `C(a,b,c)=|a|+|b|+|c|`.
- Comparação determinística: primeiro menor `E`, depois menor `C`, depois ordem lexicográfica dos coeficientes.

## Lema 1 — Forma fechada do erro

Para `(x,y)∈D`, a soma `s=x+y` só pode ser `0`, `1` ou `2`, e `R(s-2)=0`. Nos quatro casos `f` produz `(0,a,a,2a+b)`. Assim:

`E(a,b,c)=2(a-1)²+(2a+b)²`.

É uma igualdade algébrica exata em `ℤ`/`ℚ` e não depende do treinamento ou das escolhas do sintetizador.

## Teorema 1 — Correção total para XOR em D

Para `a=1, b=-2, c=0`, temos `E=0`; como os quatro somandos da definição de `E` são quadrados não negativos, cada diferença `f(x,y)-T(x,y)` é zero. Portanto, `∀ (x,y)∈D, f(x,y)=T(x,y)`.

Essa é uma prova matemática de **correção total da tarefa finita**. Não diz nada sobre entradas fora de `D` nem sobre inteligência geral.

## Teorema 2 — Optimalidade da solução

Para todos `(a,b,c)`, `E(a,b,c)≥0`. Logo qualquer solução com `E=0` é minimizadora global **da métrica E** para essa tarefa. No raio 2, `nucleo_evolucao.py` enumera 125 combinações e confere a escolha ótima pelo desempate descrito acima. A escolha particular `[1,-2,0]` tem complexidade secundária `3`.

## Teorema 3 — Melhoria estrita das gerações aceitas

As gerações observadas são `r=0` com `E=2`, `r=1` com `E=1`, e `r=2` com `E=0`. O verificador exige, independentemente do gerador, `E(r+1)<E(r)` para cada transição; portanto a sequência é estritamente decrescente no domínio `D`. A propriedade de melhoria de `E` **não implica** melhor desempenho em outros conjuntos de dados ou funções-alvo.

## Teorema 4 — Equivalência das reescritas aceitas (relativo às regras)

A transformação da IR 1.0 para a IR otimizada 1.1 é uma sequência de instâncias de equivalências locais, como `x+0 = x` e `relu(relu(x))=relu(x)` para os operadores e formas autorizados. `validar_otimizacao` exige que cada nó do grafo resultante seja a cópia do nó original com remapeamento coerente ou uma instância permitida da regra. As tabelas dos parâmetros, símbolos, perdas e comandos são igualmente preservadas sob o mapeamento. **Assumindo** a semântica e a correção das regras locais e do verificador, o programa otimizado possui a mesma semântica do original para toda entrada dentro dos domínios de definição dos operadores.

Isso não equivale a uma demonstração formal em Lean da implementação inteira, e não prova que um núcleo Python arbitrário é correto por construção.

## Limites da base de confiança

A base de confiança inclui: aritmética exata `fractions.Fraction`, parser `.omega`, compilador da IR, avaliação da linguagem, núcleo finito `nucleo_evolucao.py` e verificador estrutural `otimizador_v1.py`. O verificador finito **não chama o sintetizador**; a independência é arquitetural, não uma garantia de ausência de bugs correlacionados. SHA-256 é um mecanismo de integridade operacional, não uma assinatura de autenticidade. O script Lean 4 contém quatro metas inteiras que requerem verificação real com Lean instalado.

## O que não foi provado

Não foi demonstrado: autocorreção ilimitada, auto-hospedagem do compilador, descoberta automática de novas táticas matemáticas, melhoria cognitiva genérica, alinhamento de agentes arbitrários, invariância sob todos os ambientes, desempenho de redes grandes, segurança de hot-swap de binários, nem resolução de incompletude de Gödel/Löb.

Uma reivindicação de **IA autoevolutiva geral matematicamente provada** exigiria definições precisas de inteligência, ambientes, métrica de progresso, recursos computacionais e modelo de segurança, além de teoremas e evidências que este protótipo ainda não possui.
