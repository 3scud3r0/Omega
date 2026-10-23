"""Retropropagação exata sobre nós tensoriais, sem expandir @ em produtos escalares.

O grafo direto opera com escalares, vetores e matrizes de Fraction. Cada nó
registra funções locais de produto vetor-Jacobiano (VJP). O verificador de
certificados é outro algoritmo, baseado em polinômios escalares expandidos.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

from .algebra import MAX_EXPONENT, normalizar
from .sintaxe import Binario, Chamada, ErroOmega, Expressao, Lista, Numero, Unario, Variavel

Valor = Fraction | tuple
MAX_NOS = 10000
MAX_PROF = 150


def forma(v: Valor) -> tuple[int, ...]:
    if not isinstance(v, tuple):
        return ()
    if not v or len(v) > 32:
        raise ErroOmega('Dimensão tensorial inválida na diferenciação')
    f = forma(v[0])
    if any(forma(x) != f for x in v):
        raise ErroOmega('Tensor não retangular na diferenciação')
    if len(f) > 1:
        raise ErroOmega('Somente matrizes e vetores são suportados')
    return (len(v), *f)


def elementos(v):
    if isinstance(v, tuple):
        for x in v:
            yield from elementos(x)
    else:
        yield v


def map1(fn, v):
    return tuple(map1(fn, x) for x in v) if isinstance(v, tuple) else fn(v)


def map2(fn, a, b):
    if forma(a) != forma(b):
        raise ErroOmega('Gradientes tensoriais de formas incompatíveis')
    if isinstance(a, tuple):
        return tuple(map2(fn, x, y) for x, y in zip(a, b))
    return fn(a, b)


def soma(a, b):
    return map2(lambda x, y: x + y, a, b)


def oposto(v):
    return map1(lambda x: -x, v)


def escala(v, s):
    return map1(lambda x: x * s, v)


def produto_total(a, b) -> Fraction:
    return sum((x*y for x, y in zip(elementos(a), elementos(b))), Fraction(0))


def transpor(a):
    if len(forma(a)) != 2:
        raise ErroOmega('Transposição exige matriz')
    return tuple(tuple(a[i][j] for i in range(len(a))) for j in range(len(a[0])))


def matmul(a, b):
    fa, fb = forma(a), forma(b)
    if len(fa) != 2 or len(fb) not in (1, 2) or fa[1] != fb[0]:
        raise ErroOmega('Multiplicação matricial exige dimensões compatíveis')
    if len(fb) == 1:
        return tuple(sum((a[i][k]*b[k] for k in range(fa[1])), Fraction(0))
                     for i in range(fa[0]))
    return tuple(tuple(sum((a[i][k]*b[k][j] for k in range(fa[1])), Fraction(0))
                       for j in range(fb[1])) for i in range(fa[0]))


@dataclass
class No:
    valor: Valor
    pais: list[tuple[int, Callable[[Valor], Valor]]]
    variavel: str = ''


def retropropagar_tensores(expr: Expressao, definicoes: dict[str, Expressao],
                           estado: dict[str, Fraction]) -> dict[str, Fraction]:
    """Produz d(loss)/d(coordenada) de uma única passagem reversa tensorial."""
    fita: list[No] = []

    def criar(valor, pais=None, variavel=''):
        forma(valor)
        if len(fita) >= MAX_NOS:
            raise ErroOmega('Limite de nós para autodiferenciação tensorial excedido')
        fita.append(No(valor, pais or [], variavel))
        return len(fita)-1

    def construir(e, nivel=0, visitados=frozenset()):
        if nivel > MAX_PROF:
            raise ErroOmega('Expressão de gradiente excessivamente profunda')
        if isinstance(e, Numero):
            return criar(e.valor)
        if isinstance(e, Variavel):
            if e.nome in definicoes:
                if e.nome in visitados:
                    raise ErroOmega('Referência tensorial circular')
                return construir(definicoes[e.nome], nivel+1, visitados | {e.nome})
            if e.nome not in estado:
                raise ErroOmega('Variável não definida: '+e.nome)
            return criar(estado[e.nome], variavel=e.nome)
        if isinstance(e, Lista):
            indices = [construir(x, nivel+1, visitados) for x in e.elementos]
            valor = tuple(fita[i].valor for i in indices)
            pais = [(i, lambda grad, j=j: grad[j]) for j, i in enumerate(indices)]
            return criar(valor, pais)
        if isinstance(e, Unario) and e.operador == '-':
            i = construir(e.argumento, nivel+1, visitados)
            return criar(oposto(fita[i].valor), [(i, oposto)])
        if isinstance(e, Chamada):
            indices = [construir(a, nivel+1, visitados) for a in e.argumentos]
            vals = [fita[i].valor for i in indices]
            if e.funcao == 'dot' and len(vals) == 2 and len(forma(vals[0])) == 1 and forma(vals[0]) == forma(vals[1]):
                a, b = vals
                return criar(produto_total(a, b), [(indices[0], lambda g, b=b: escala(b, g)),
                                                  (indices[1], lambda g, a=a: escala(a, g))])
            if e.funcao == 'transposta' and len(vals) == 1:
                return criar(transpor(vals[0]), [(indices[0], transpor)])
            raise ErroOmega('Chamada inválida no gradiente tensorial')
        if isinstance(e, Binario):
            i = construir(e.esquerda, nivel+1, visitados)
            j = construir(e.direita, nivel+1, visitados)
            a, b = fita[i].valor, fita[j].valor
            op = e.operador
            if op == '+':
                if forma(a) != forma(b):
                    raise ErroOmega('Adição tensorial incompatível')
                return criar(soma(a, b), [(i, lambda g: g), (j, lambda g: g)])
            if op == '-':
                return criar(soma(a, oposto(b)), [(i, lambda g: g), (j, oposto)])
            if op == '*':
                if not forma(a) and not forma(b):
                    return criar(a*b, [(i, lambda g, b=b: g*b), (j, lambda g, a=a: g*a)])
                if not forma(a):
                    return criar(escala(b, a), [(i, lambda g, b=b: produto_total(g, b)),
                                               (j, lambda g, a=a: escala(g, a))])
                if not forma(b):
                    return criar(escala(a, b), [(i, lambda g, b=b: escala(g, b)),
                                               (j, lambda g, a=a: produto_total(g, a))])
                raise ErroOmega('Use @ para multiplicação matricial')
            if op == '@':
                v = matmul(a, b)
                if len(forma(b)) == 1:
                    return criar(v, [(i, lambda g, b=b: tuple(tuple(g[r]*b[c] for c in range(len(b))) for r in range(len(g)))),
                                      (j, lambda g, a=a: matmul(transpor(a), g))])
                return criar(v, [(i, lambda g, b=b: matmul(g, transpor(b))),
                                  (j, lambda g, a=a: matmul(transpor(a), g))])
            if op == '/':
                c = normalizar(e.direita).constante_pura()
                if forma(a) or c == 0:
                    raise ErroOmega('Divisão tensorial inválida ou por zero')
                return criar(a/c, [(i, lambda g, c=c: g/c)])
            if op == '^':
                c = normalizar(e.direita).constante_pura()
                if forma(a) or c.denominator != 1 or not 0 <= c <= MAX_EXPONENT:
                    raise ErroOmega('Expoente tensorial inválido')
                k = int(c)
                return criar(a**k, [(i, lambda g, a=a, k=k: g*k*a**(k-1) if k else Fraction(0))])
        raise ErroOmega('Operação inválida na autodiferenciação tensorial')

    raiz = construir(expr)
    if forma(fita[raiz].valor):
        raise ErroOmega('Perda deve ser escalar para retropropagação')
    adjuntos = [map1(lambda _: Fraction(0), no.valor) for no in fita]
    adjuntos[raiz] = Fraction(1)
    for i in range(len(fita)-1, -1, -1):
        for pai, vjp in fita[i].pais:
            adjuntos[pai] = soma(adjuntos[pai], vjp(adjuntos[i]))
    resultado = {nome: Fraction(0) for nome in estado}
    for no, adj in zip(fita, adjuntos):
        if no.variavel:
            resultado[no.variavel] += adj
    return resultado
