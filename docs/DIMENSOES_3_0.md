# OM-013 — dimensões verificáveis

`omega/dimensions.py` fornece contratos de formas sem executar tensores.
Dimensões podem ser constantes positivas em 1..2048 ou símbolos nomeados.
As regras de soma, produto, transposta, escala, divisão, potência, soma total
e produto interno estabelecem as igualdades necessárias. Uma classe de
equivalência que contém constantes diferentes é rejeitada.

```python
from omega.dimensions import dimension_contract
product = dimension_contract('@', (('m', 'k'), ('n', 'p')))
product.specialize({'m': 2, 'k': 3, 'n': 3, 'p': 4})  # rational[2,4]
# n=5 seria rejeitado: k e n precisam coincidir.
```

Todos os símbolos precisam receber valores antes da especialização. Formas de
entrada e saída respeitam o limite de um milhão de células. Não há dimensões
dinâmicas implicitamente aceitas nem inferência de expressões aritméticas
gerais sobre dimensões. `omega-dimensions-1` serializa as obrigações; o leitor
reconstrói as regras e rejeita resultados ou igualdades adulterados.

`compile_ir` agora verifica cada nó, inclusive temporários sem nome. Parâmetros
precisam concordar com seus inicializadores; empilhamentos precisam ser
retangulares. Grafos sem nós são permitidos para programas só de identidades.
`omega native-shapes exemplos/rede_profunda.omega` emite o certificado
`omega-graph-shapes-1`. O verificador recalcula as formas e o digest dos
operadores, dependências, dimensões e vínculos de parâmetros.

Esse digest vincula **somente as dimensões**. Ele não certifica valores,
comandos, provas de identidades, diferenciação ou a tradução para C. A
validação integral/versionamento da IR pertence à OM-014. A linguagem de
superfície existente continua usando dimensões concretas; contratos simbólicos
estão disponíveis na API para futuras especializações.

Os testes comparam 1.235 instâncias de operadores/formas pequenas contra duas
regras de tipos existentes, verificam todos os nós do corpus tensorial e
recusam certificados, dimensões, dependências e inicializadores adulterados.
Também cobrem conflitos transitivos, bindings ausentes e orçamentos de células.
