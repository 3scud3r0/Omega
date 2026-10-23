"""Expansão simbólica de vetores e matrizes para a AST escalar de Ômega.

Esta parte é o *produtor* de transformações, não é o verificador independente.
Valores tensoriais são tuplas imutáveis de expressões simbólicas escalares.
Não há NumPy, ponto flutuante, GPU ou execução de código arbitrário.
"""
from __future__ import annotations

from typing import TypeAlias

from .sintaxe import Binario, Chamada, ErroOmega, Expressao, Lista, Numero, Unario, Variavel

Valor: TypeAlias = Expressao | tuple  # vetor = tupla de escalares; matriz = tupla de vetores
MAX_DIM = 32
MAX_PROF = 90
MAX_NOS = 3500


def formato(v: Valor) -> tuple[int, ...]:
    if not isinstance(v, tuple):
        return ()
    if len(v) == 0 or len(v) > MAX_DIM:
        raise ErroOmega(f"Cada dimensão de tensor deve estar entre 1 e {MAX_DIM}")
    sub = [formato(i) for i in v]
    if len(set(sub)) != 1:
        raise ErroOmega("Tensor não retangular ou elementos com tipos incompatíveis")
    if len(sub[0]) >= 2:
        raise ErroOmega("Ômega 0.3 aceita somente escalares, vetores e matrizes")
    return (len(v), *sub[0])


def tipo_tensor(v: Valor) -> str:
    f = formato(v)
    if not f:
        return 'Escalar'
    return f'Vetor[{f[0]}]' if len(f) == 1 else f'Matriz[{f[0]},{f[1]}]'


def mapear(f, a: Valor, b: Valor | None = None) -> Valor:
    if b is not None and formato(a) != formato(b):
        raise ErroOmega(f"Dimensões incompatíveis: {tipo_tensor(a)} e {tipo_tensor(b)}")
    if isinstance(a, tuple):
        if b is None:
            return tuple(mapear(f, x) for x in a)
        assert isinstance(b, tuple)
        return tuple(mapear(f, x, y) for x, y in zip(a, b))
    return f(a) if b is None else f(a, b)


def soma(exprs: list[Expressao]) -> Expressao:
    if not exprs:
        return Numero(__import__('fractions').Fraction(0))
    acc = exprs[0]
    for x in exprs[1:]:
        acc = Binario('+', acc, x)
    return acc


def produto_interno(a: Valor, b: Valor) -> Expressao:
    f1, f2 = formato(a), formato(b)
    if len(f1) != 1 or f1 != f2:
        raise ErroOmega(f"dot exige vetores de mesmo tamanho; recebidos {tipo_tensor(a)} e {tipo_tensor(b)}")
    assert isinstance(a, tuple) and isinstance(b, tuple)
    return soma([Binario('*', x, y) for x, y in zip(a, b)])


def matmul(a: Valor, b: Valor) -> Valor:
    fa, fb = formato(a), formato(b)
    if len(fa) != 2 or len(fb) not in (1, 2) or fa[1] != fb[0]:
        raise ErroOmega(f"@ exige Matriz[m,n] @ Vetor[n] ou Matriz[n,p]; recebidos {tipo_tensor(a)} e {tipo_tensor(b)}")
    assert isinstance(a, tuple) and isinstance(b, tuple)
    if len(fb) == 1:
        return tuple(soma([Binario('*', a[i][k], b[k]) for k in range(fa[1])])
                     for i in range(fa[0]))
    return tuple(tuple(soma([Binario('*', a[i][k], b[k][j]) for k in range(fa[1])])
                       for j in range(fb[1])) for i in range(fa[0]))


def expandir(expr: Expressao, definicoes: dict[str, Expressao] | None = None,
             nivel: int = 0, pilha: frozenset[str] = frozenset()) -> Valor:
    """Aplica as regras de álgebra tensorial sem avaliar os parâmetros."""
    if nivel > MAX_PROF:
        raise ErroOmega("Expressão tensorial excessivamente profunda")
    env = definicoes or {}
    if isinstance(expr, (Numero, Variavel)):
        if isinstance(expr, Variavel) and expr.nome in env:
            if expr.nome in pilha:
                raise ErroOmega("Referência tensorial circular")
            return expandir(env[expr.nome], env, nivel+1, pilha | {expr.nome})
        return expr
    if isinstance(expr, Lista):
        v = tuple(expandir(x, env, nivel+1, pilha) for x in expr.elementos)
        formato(v)
        return v
    if isinstance(expr, Unario):
        a = expandir(expr.argumento, env, nivel+1, pilha)
        if expr.operador != '-':
            raise ErroOmega('Operador unário desconhecido')
        return mapear(lambda x: Unario('-', x), a)
    if isinstance(expr, Chamada):
        args = [expandir(x, env, nivel+1, pilha) for x in expr.argumentos]
        if expr.funcao == 'dot' and len(args) == 2:
            return produto_interno(*args)
        if expr.funcao == 'transposta' and len(args) == 1:
            matriz = args[0]
            if len(formato(matriz)) != 2:
                raise ErroOmega('transposta exige uma matriz')
            return tuple(tuple(matriz[i][j] for i in range(len(matriz)))
                         for j in range(len(matriz[0])))
        raise ErroOmega(f"Função tensorial desconhecida ou argumentos inválidos: {expr.funcao}")
    if isinstance(expr, Binario):
        a = expandir(expr.esquerda, env, nivel+1, pilha)
        b = expandir(expr.direita, env, nivel+1, pilha)
        op = expr.operador
        if op == '@':
            return matmul(a, b)
        if op in ('+', '-'):
            return mapear(lambda x,y: Binario(op,x,y), a, b)
        if op == '*':
            fa, fb = formato(a), formato(b)
            if not fa and not fb:
                return Binario(op, a, b)
            if not fa:
                return mapear(lambda x: Binario(op, a, x), b)
            if not fb:
                return mapear(lambda x: Binario(op, x, b), a)
            raise ErroOmega('Multiplicação tensorial usa @; * é só escala ou escala × tensor')
        if op in ('/', '^') and not formato(a) and not formato(b):
            return Binario(op, a, b)
        raise ErroOmega(f"Operador {op!r} incompatível com {tipo_tensor(a)} e {tipo_tensor(b)}")
    raise ErroOmega('Expressão tensorial desconhecida')


def para_ast(v: Valor) -> Expressao:
    if isinstance(v, tuple):
        return Lista(tuple(para_ast(x) for x in v))
    return v


def visitar_escalas(v: Valor, fn) -> None:
    if isinstance(v, tuple):
        for x in v:
            visitar_escalas(x, fn)
    else:
        fn(v)


def contar_nos(v: Valor) -> int:
    if isinstance(v, tuple):
        return 1+sum(contar_nos(x) for x in v)
    if isinstance(v, (Numero, Variavel)):
        return 1
    if isinstance(v, Unario):
        return 1+contar_nos(v.argumento)
    if isinstance(v, Binario):
        return 1+contar_nos(v.esquerda)+contar_nos(v.direita)
    raise ErroOmega('Expressão de resultado tensorial malformada')


def conferir_limites(v: Valor) -> Valor:
    formato(v)
    if contar_nos(v) > MAX_NOS:
        raise ErroOmega(f'Expansão excede {MAX_NOS} nós; use tensores menores')
    return v
