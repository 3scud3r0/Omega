# OM-014 — IR canônica, tipada e versionada

```sh
omega native-ir exemplos/rede_profunda.omega --saida rede.typed.json
omega validate-ir rede.typed.json
```

`omega.typed_ir.TypedIR` é um objeto imutável contendo os bytes validados.
Seu formato é `omega-typed-ir-1`, `schema_version` é `1.0.0` e o dialeto é
`tensor`. Esse número versiona o esquema, não anuncia uma release Ômega 3.0.
O envelope contém `graph` (IR tensorial/identidades existente) e `types`, uma
anotação racional/forma para cada nó. A importação legada é explícita por
`TypedIR.from_legacy`; não se aceitam versões desconhecidas por aproximação.

A codificação usa UTF-8 válido, chaves ordenadas por ponto de código Unicode,
separadores compactos e inteiros naturais limitados nos campos estruturais.
Não é uma implementação de RFC 8785. Literais racionais são strings reduzidas,
com denominador positivo, sem zeros iniciais, `-0`, denominador 1 ou notação
exponencial. Inteiros racionais grandes são analisados em blocos pequenos;
o limite global de conversão de inteiros Python permanece ativo.

O leitor recusa chaves JSON duplicadas, campos extras, bools, null, floats,
NaN, Unicode inválido e espaços excedentes. O limite é 16 MiB, profundidade
220 e 500.000 valores estruturais; cada AST de identidade tem orçamento de
12.000 nós e profundidade 200. Arquivos são lidos até o limite mais um byte.
O hash SHA-256 identifica os bytes canônicos. Dicionários exportados são cópias.

Antes de aceitar o envelope, o validador reconstrói as dimensões, confere
aridades e dependências anteriores de cada nó, literais e expoentes,
inicializadores, nomes únicos e correspondência integral das tabelas.
Comandos precisam ter exatamente seus campos e referências autorizadas;
declarações precedem comandos que usam seus nomes. ASTs de identidades são
dados tipados limitados aos operadores suportados pelo motor de provas.
O resultado declarado de tipos precisa coincidir com o resultado recalculado.
`compile_ir` aplica esse validador completo ao frontend auto-hospedado.

A conversão preserva todos os nós, tabelas, comandos, literais e sua ordem.
O envelope não reinterpreta o histórico de reescritas da IR legada nem muda a
semântica existente de referência às tabelas finais. A IR procedural ainda
não faz parte desse esquema tensorial. A API legada de referência continua
disponível para compatibilidade; consumidores que exigem a nova fronteira
devem carregar `TypedIR`, em vez de desserializar JSON diretamente.

**Validação de dados e tipos não é admissão de provas.** `provar 1 == 2`
tem uma AST bem formada e operandos do mesmo tipo, mas só pode ser admitido
após o motor de provas demonstrar a identidade. Tampouco o digest autoriza
execução ou certifica o backend C. Sandbox e conferência Lean continuam
necessários para execução certificada.

A validação compara round trips dos grafos originais e otimizados de todo o
corpus tensorial e inclui mutações de esquema, tipos, literais, tabelas,
comandos e ASTs, JSON ambíguo, limites e uso real da CLI.
