# OM-015 — SSA, dependências e dominância

`omega.ssa` representa blocos, valores tipados, terminadores e nós phi em
objetos imutáveis. Cada valor tem uma única definição. O verificador constrói
predecessores, sucessores e cadeias def-use; calcula dominadores, dominador
imediato e fronteiras de dominância por ponto fixo. A ordem dos blocos no
objeto de entrada não muda o relatório.

Usos normais exigem que a definição domine o bloco e anteceda a instrução
quando estão no mesmo bloco. Um operando phi é um uso **na aresta do
predecessor**, não na posição textual do phi: isso permite realimentação
válida em laços, mas impede ler um valor definido apenas no outro ramo.
Cada phi tem exatamente um operando por predecessor e tipos coincidentes.
Phis precedem instruções comuns. Inputs pertencem à entrada, branches exigem
escalares e os demais operadores seguem os contratos tensoriais.

Definições repetidas, referências ausentes, usos sem dominância, formas
incompatíveis, destinos inexistentes e blocos inacessíveis são erros. A
entrada não tem predecessores; grafos limitam-se a 256 blocos, 12.000
definições e 120.000 referências. O relatório é `omega-ssa-analysis-1`;
`verify_analysis` recalcula a análise e compara sua codificação estrita.
Uma anotação booleana não pode se passar pelo índice inteiro 0 ou 1.

```sh
omega native-ssa exemplos/rede_profunda.omega
```

O adaptador exige uma `TypedIR` validada. O DAG tensorial já atribui um id por
nó; ele se torna um bloco SSA com parâmetros como inputs e símbolos nomeados
como resultados. O relatório vincula o hash da IR canônica e registra seu
escopo: **uma avaliação pura do grafo tensorial**. Não se afirma que comandos
mutáveis de treinamento foram convertidos para SSA, nem que este adaptador
implementa o lowering do heap/controle procedural. O analisador geral também
aceita CFGs com diamantes e laços fornecidos pela API, que são exercitados
diretamente nos testes. Essa etapa fornece análise e verificações estruturais,
sem otimização ou alteração de executáveis.

Os testes conferem def-use e phis em diamantes/laços, recusam usos cruzados
entre ramos e referências futuras e analisam o corpus tensorial. Em 80 CFGs
reproduzíveis, dominadores são comparados a um oráculo independente que remove
cada bloco e verifica alcançabilidade. Fronteiras são conferidas pela sua
definição, separadamente do algoritmo de dominadores imediatos.
