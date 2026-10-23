"""Diferenciação automática REVERSA exata em AST escalar expandida.

Registra um tape com valores racionais e derivadas locais. Uma única passagem
reversa calcula a derivada de uma perda escalar em relação a todos os parâmetros.
O verificador usa derivação polinomial independente em omega.nucleo.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .algebra import MAX_EXPONENT, normalizar
from .sintaxe import Binario, ErroOmega, Expressao, Numero, Unario, Variavel


@dataclass
class No:
    valor: Fraction
    pais: tuple[tuple[int, Fraction], ...]
    variavel: str = ''


def retropropagar(expr: Expressao, estado: dict[str, Fraction]) -> dict[str, Fraction]:
    fita: list[No] = []
    LIMITE = 5000

    def adicionar(valor: Fraction, pais: tuple[tuple[int, Fraction], ...]=(), variavel='') -> int:
        if len(fita) >= LIMITE:
            raise ErroOmega(f'Grafo de diferenciação excede {LIMITE} nós')
        fita.append(No(valor, pais, variavel))
        return len(fita)-1

    def construir(e: Expressao, profundidade=0) -> int:
        if profundidade > 150:
            raise ErroOmega('Grafo de diferenciação profundo demais')
        if isinstance(e, Numero):
            return adicionar(e.valor)
        if isinstance(e, Variavel):
            if e.nome not in estado:
                raise ErroOmega(f'Parâmetro ausente no estado: {e.nome}')
            return adicionar(estado[e.nome], variavel=e.nome)
        if isinstance(e, Unario) and e.operador == '-':
            x = construir(e.argumento, profundidade+1)
            return adicionar(-fita[x].valor, ((x,Fraction(-1)),))
        if isinstance(e, Binario):
            op = e.operador
            x = construir(e.esquerda,profundidade+1)
            a = fita[x].valor
            if op == '+':
                y = construir(e.direita,profundidade+1)
                return adicionar(a+fita[y].valor, ((x,Fraction(1)),(y,Fraction(1))))
            if op == '-':
                y = construir(e.direita,profundidade+1)
                return adicionar(a-fita[y].valor, ((x,Fraction(1)),(y,Fraction(-1))))
            if op == '*':
                y = construir(e.direita,profundidade+1)
                b = fita[y].valor
                return adicionar(a*b, ((x,b),(y,a)))
            if op == '/':
                divisor = normalizar(e.direita).constante_pura()
                if divisor == 0:
                    raise ErroOmega('Divisão por zero')
                return adicionar(a/divisor, ((x,Fraction(1)/divisor),))
            if op == '^':
                expoente = normalizar(e.direita).constante_pura()
                if expoente.denominator != 1 or not 0 <= expoente <= MAX_EXPONENT:
                    raise ErroOmega(f'Expoente deve ser inteiro entre 0 e {MAX_EXPONENT}')
                grau = int(expoente)
                derivada = grau*a**(grau-1) if grau else Fraction(0)
                return adicionar(a**grau, ((x,derivada),))
        raise ErroOmega('Diferenciação reversa aceita expressões escalares polinomiais')

    raiz = construir(expr)
    adjuntos = [Fraction(0) for _ in fita]
    adjuntos[raiz] = Fraction(1)
    for i in range(len(fita)-1,-1,-1):
        for origem,derivada_local in fita[i].pais:
            adjuntos[origem] += adjuntos[i]*derivada_local
    saida = {nome: Fraction(0) for nome in estado}
    for no, adj in zip(fita,adjuntos):
        if no.variavel:
            saida[no.variavel] += adj
    return saida
