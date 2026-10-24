# OM-012 — inferência de tipos antes da execução

`omega native-types arquivo.omega` infere tipos sem executar o programa.
`native-build` exige essa checagem antes de chamar GCC. O frontend nativo
continua responsável por parsing/lowering; o novo passe é uma conferência
independente no orquestrador. Em `compile_ir`, os tipos públicos inferidos
também precisam concordar com as formas emitidas pelo frontend auto-hospedado.

```sh
.venv/bin/python -m omega native-types exemplos/rede_profunda.omega
.venv/bin/python -m omega native-types exemplos/procedural/soma.omega
```

## Núcleo numérico e tensorial

`omega/typesystem.py` infere `NumericType(shape)`, com elementos racionais,
diretamente da sintaxe. Não materializa zeros, identidades, produtos matriciais
ou polinômios para descobrir um tipo. Um escalar tem forma `()`. Vetores e
matrizes carregam dimensões concretas; aridade, retangularidade, ordem,
declarações, referências e operadores são conferidos antes de gerar o binário.
O passe também abrange gradientes, taxas, reescritas e enunciados de identidades.
Variáveis livres de uma identidade universal representam escalares racionais;
fora desses enunciados, nomes não declarados são erros.

As tabelas produzidas são imutáveis e serializáveis. `ProgramTypes.to_dict()`
usa `omega-inferred-types-1`. Os literais permanecem textuais durante a análise:
uma constante com milhares de dígitos não precisa virar um inteiro Python para
que seu tipo escalar seja conhecido. Dimensões e expoentes têm limites pequenos
explícitos; nenhum limite global de segurança de inteiros Python é desabilitado.

Este passe limita a fonte a 256 Ki caracteres, a expressão a 12.000 nós e a
profundidade a 200. Dimensões concretas ficam em 1..2048, ordem até 2 e um milhão
de células por nó. Uma violação de orçamento é diagnosticada, não aceita com um
tipo inventado. Aritmética racional continua exata no backend GMP.

## Dialeto procedural

`omega/procedural_types.py` faz análise abstrata contextual, partindo de
`principal`, sem calcular aritmética de usuário ou realizar I/O. As funções
chamadas são verificadas nas suas instâncias de tipos; funções restantes também
recebem uma checagem não instanciada. Esses registros contextuais não constituem
uma interface polimórfica universal nem uma prova formal de todas as entradas.
`omega-procedural-types-1` identifica os dois modos no relatório.

O passe verifica aridades, referências, escopos, retorno numérico de `principal`,
operadores, builtins e uso de listas/objetos. Tipos numéricos e strings podem
especializar a mesma função em chamadas distintas. Refinamentos `isnum`, `isstr`
e `islist` são reconhecidos em condicionais e curto-circuito. Um guard que
termina por `fail` pode estabelecer a condição do caminho que continua.

Referências mutáveis são acompanhadas: um acesso por índice desconhecido pode
representar vários objetos. Escritas precisam respeitar todos os alvos possíveis.
Loops usam aproximação conservadora até um ponto fixo; listas perdem informação
de posições quando necessário. A análise de uma chamada recursiva não reutiliza
fatos precisos de heap para argumentos que a chamada pode modificar.

Dados de `parsejson` sem um produtor conhecido permanecem opacos. Refinamentos
conferem seus quatro tipos de valor possíveis no codec: número, string, lista
ou objeto. Escrever em um container opaco não torna leituras posteriores
automaticamente tipadas. Um objeto tipado que escapa para esse container também
perde as suposições mutáveis precisas, pois pode ser alterado por outro alias.
Round trips conhecidos `parsejson(json(x))` usam snapshots de tipos, sem atribuir
ao resultado a identidade mutável do objeto original.

A análise procedural conta até 120.000 operações de análise, incluindo passeios
pelos tipos, até 100 chamadas aninhadas e oito iterações para estabilizar um
invariante de loop. Tipos recursivos de containers e invariantes que não possam
ser estabelecidos são recusados. Algumas construções válidas no runtime dinâmico
podem ser rejeitadas por essa análise conservadora. Os contratos estáticos de
builtins também evitam usos pouco informativos do runtime legado, como `len(3)`.

O bootstrap confiável do compilador continua sendo um procedimento separado,
comparando fontes C e binários em múltiplos estágios. O executável baixo nível
do frontend e o estágio zero são componentes do bootstrap, não certificados de
que todo uso direto do dialeto legado passou por essa nova análise independente.

## Limites e evidência

Tipo correto não prova que um programa termina ou que todo valor satisfaz um
contrato dinâmico. Divisão por zero, chave ausente, índice fora do intervalo,
conversão de texto inválido, retorno não integral na fronteira C e orçamento
esgotado continuam produzindo erros. Guards explícitos podem recusar dados em
execução; isso não autoriza operações incompatíveis fora do caminho refinado.
A formalização completa dos passes e do heap pertence às tarefas formais
posteriores. Esta entrega não a substitui por testes.

Os testes incluem inferência de matrizes grandes sem executar o motor, tipos de
todo o corpus numérico contra o frontend nativo, erro antes de invocar GCC,
aliases, mutação recursiva, escape para JSON opaco e ausência de I/O no checker.
Uma matriz de **208 combinações de operador e tipos** é comparada ao runtime C
real, executado em sandbox, para identificar tanto aceitações indevidas quanto
rejeições inconsistentes nesse domínio finito.

Uma regressão adicional corrige a emissão de controles ASCII em strings: escapes
JSON `\u0001` não são literais C válidos. Estágio zero e frontend auto-hospedado
agora emitem escapes C canônicos, com octais de três dígitos quando necessário.
O teste cobre os controles não NUL, DEL, aspas, barra invertida e UTF-8, e exige
igualdade do C emitido nos dois caminhos e preservação do valor executado.
