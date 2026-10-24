# Compilador Ômega escrito em Ômega

`omega_selfhost/compiler.omega` é o compilador de produção. Ele inclui o lexer,
o parser procedural e tensorial, a verificação de formas, a construção da IR,
a expansão de identidades, o otimizador por testemunhas e a emissão de GNU C.
Não importa Python nem invoca outro parser/compilador da linguagem.

O novo dialeto procedural fornece os recursos usados para escrever o compilador:

```omega
funcao soma(xs) {
  var resultado = 0;
  var i = 0;
  enquanto (i < len(xs)) {
    resultado = resultado + xs[i];
    i = i + 1;
  }
  retornar resultado;
}
funcao principal() {
  print(text(soma([1/3, 1/6])));
  retornar 0;
}
```

Há funções recursivas, variáveis locais, `se`/`senao`, `enquanto`, `parar`,
`retornar`, listas, objetos, strings UTF-8, IO e racionais GMP. As operações
`&&` e `||` têm curto-circuito. Argumentos e operandos são avaliados da esquerda
para a direita: o emissor usa temporários em expressões de bloco GNU C para
preservar essa ordem. Strings não aceitam NUL embutido. Chamadas e laços têm
combustível; a recursão é limitada a 512 chamadas. `OMEGA_FUEL` controla o orçamento.
`len` e os índices/slices de strings contam bytes UTF-8; a leitura de
identificadores e dígitos Unicode reconhece os caracteres completos.

As primitivas genéricas incluem `len`, `get`, `put`, `push`, `keys`, `has`,
`slice`, `join`, `text`, `number`, `json`, `parsejson`, `read`, `write`, `arg`,
`argc`, `print` e `fail`. O codec JSON exige conversão explícita de racionais
não inteiros para strings. Ele não é um avaliador de código.
Esse codec cobre os tipos necessários à IR: objetos, arrays, strings e números;
não implementa os literais JSON `true`, `false` e `null`.

## Bootstrap reproduzível

1. `bootstrap.py` compila somente o dialeto procedural e gera `stage0.c`.
2. O compilador C/GMP gera `omegac-stage0`.
3. Esse executável compila `compiler.omega` e gera `stage1.c`.
4. Compilar `stage1.c` gera o estágio 1, que gera `stage2.c`.
5. O estágio 2 recompila a fonte mais uma vez e gera `stage3.c`.
6. Comparar todos os fontes C e os binários estabilizados por SHA256.

O relatório em `build/selfhost/bootstrap.json` registra os hashes. A comparação
de binários remove a tabela de símbolos de depuração para evitar diferenças
causadas somente pelos nomes `stage1.c` e `stage2.c`. As verificações de código C
permanecem ativas. Um lock evita bootstraps simultâneos conflitantes.

```sh
.venv/bin/python -m omega bootstrap
build/selfhost/omegac-stage2 programa.omega /tmp/programa.c
cc -std=gnu11 -O2 -I omega_selfhost /tmp/programa.c -lgmp -o /tmp/programa
/tmp/programa
```

Para fontes tensoriais, `--ir` emite a IR JSON. `--optimize` emite C otimizado e
uma testemunha `.opt.json`; `--optimized-ir` emite a IR otimizada com testemunha.
O comando de produção `omega native-build --optimize` verifica essa testemunha e
suas provas universais antes da entrega. A saída direta do compilador de baixo
nível não substitui esse passo de admissão.

Os identificadores Unicode e os dígitos decimais Unicode são aceitos, incluindo
as formas utilizadas pelo frontend histórico. A IR mantém literais racionais
normalizados. Os testes comparam a IR produzida com a implementação de referência
para as fontes compatíveis e executam o corpus completo de exemplos.
