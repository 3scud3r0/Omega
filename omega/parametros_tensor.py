"""Representação de parâmetros vetoriais/matriciais como coordenadas escalares internas.

Coordenadas são geradas somente pelo compilador, nunca pelo código fonte Ômega.
A correspondência é imutável; somente os valores racionais mudam nos passos.
"""
from __future__ import annotations

from fractions import Fraction
from .sintaxe import ErroOmega, Expressao, Lista, Variavel

PREFIXO = '__omega_coord_'


def coordenadas(nome: str, dimensoes: tuple[int, ...]):
    """Converte as dimensões em uma árvore imutável de nomes internos."""
    if len(dimensoes) not in (1, 2) or any(not 1 <= d <= 32 for d in dimensoes):
        raise ErroOmega('Parâmetro tensorial exige Vetor[n] ou Matriz[m,n] com dimensões 1..32')
    if len(dimensoes) == 1:
        return tuple(f'{PREFIXO}{nome}_{i}' for i in range(dimensoes[0]))
    return tuple(tuple(f'{PREFIXO}{nome}_{i}_{j}' for j in range(dimensoes[1]))
                 for i in range(dimensoes[0]))


def em_ast(nomes) -> Expressao:
    if isinstance(nomes, tuple):
        return Lista(tuple(em_ast(n) for n in nomes))
    return Variavel(nomes)


def folhas(arvore):
    if isinstance(arvore, tuple):
        for sub in arvore:
            yield from folhas(sub)
    else:
        yield arvore


def remodelar(arvore, valores: dict[str, Fraction]):
    if isinstance(arvore, tuple):
        return tuple(remodelar(x, valores) for x in arvore)
    return valores[arvore]


def como_listas(arvore):
    if isinstance(arvore, tuple):
        return [como_listas(x) for x in arvore]
    return str(arvore)
