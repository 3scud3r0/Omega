"""Álgebra simbólica exata para o fragmento polinomial de Ômega.

Polinômios são mapas de monômios -> Fraction. Não há arredondamento.
A igualdade formal é igualdade das formas normais desses mapas.
"""
from __future__ import annotations

from fractions import Fraction
from .sintaxe import Binario, ErroOmega, Expressao, Numero, Unario, Variavel

Monomio = tuple[tuple[str, int], ...]
MAX_TERMS = 5000
MAX_EXPONENT = 20


class Polinomio:
    def __init__(self, termos: dict[Monomio, Fraction] | None = None):
        self.termos = {m: c for m, c in (termos or {}).items() if c != 0}
        if len(self.termos) > MAX_TERMS:
            raise ErroOmega("Expressão excede o limite de 5000 monômios")

    @staticmethod
    def constante(c: Fraction) -> "Polinomio":
        return Polinomio({(): c})

    @staticmethod
    def variavel(nome: str) -> "Polinomio":
        return Polinomio({((nome, 1),): Fraction(1)})

    def __eq__(self, outro: object) -> bool:
        return isinstance(outro, Polinomio) and self.termos == outro.termos

    def __neg__(self) -> "Polinomio":
        return Polinomio({m: -c for m, c in self.termos.items()})

    def __add__(self, outro: "Polinomio") -> "Polinomio":
        soma = dict(self.termos)
        for monomio, coef in outro.termos.items():
            soma[monomio] = soma.get(monomio, Fraction(0)) + coef
        return Polinomio(soma)

    def __sub__(self, outro: "Polinomio") -> "Polinomio":
        return self + (-outro)

    def __mul__(self, outro: "Polinomio") -> "Polinomio":
        produto: dict[Monomio, Fraction] = {}
        for m1, c1 in self.termos.items():
            for m2, c2 in outro.termos.items():
                fatores = dict(m1)
                for var, expoente in m2:
                    fatores[var] = fatores.get(var, 0) + expoente
                m = tuple(sorted((v, e) for v, e in fatores.items() if e))
                produto[m] = produto.get(m, Fraction(0)) + c1 * c2
                if len(produto) > MAX_TERMS * 2:
                    raise ErroOmega("Produto polinomial grande demais")
        return Polinomio(produto)

    def potencia(self, exp: int) -> "Polinomio":
        if not isinstance(exp, int) or not 0 <= exp <= MAX_EXPONENT:
            raise ErroOmega(f"Expoente deve ser inteiro entre 0 e {MAX_EXPONENT}")
        saida = Polinomio.constante(Fraction(1))
        base = self
        while exp:
            if exp % 2:
                saida = saida * base
            exp //= 2
            if exp:
                base = base * base
        return saida

    def constante_pura(self) -> Fraction:
        if set(self.termos).difference({()}):
            raise ErroOmega("Esta operação exige uma expressão constante")
        return self.termos.get((), Fraction(0))

    def derivar(self, nome: str) -> "Polinomio":
        saida: dict[Monomio, Fraction] = {}
        for monomio, coef in self.termos.items():
            potencias = dict(monomio)
            expoente = potencias.get(nome, 0)
            if expoente:
                if expoente == 1:
                    del potencias[nome]
                else:
                    potencias[nome] -= 1
                m = tuple(sorted(potencias.items()))
                saida[m] = saida.get(m, Fraction(0)) + coef * expoente
        return Polinomio(saida)

    def avaliar(self, ambiente: dict[str, Fraction]) -> Fraction:
        total = Fraction(0)
        for monomio, coef in self.termos.items():
            parcela = coef
            for variavel, expoente in monomio:
                if variavel not in ambiente:
                    raise ErroOmega(f"Parâmetro não definido: {variavel}")
                parcela *= ambiente[variavel] ** expoente
            total += parcela
        return total

    def variaveis(self) -> set[str]:
        return {nome for monomio in self.termos for nome, _ in monomio}

    def forma_normal(self) -> list[dict]:
        """Exibe o certificado canônico do anel Q[x1,...,xn]."""
        return [
            {"monomio": [[v, e] for v, e in m], "coeficiente": str(c)}
            for m, c in sorted(self.termos.items())
        ]


def normalizar(expr: Expressao, nivel: int = 0) -> Polinomio:
    """Compila a AST num polinômio canônico de coeficientes racionais."""
    if nivel > 200:
        raise ErroOmega("Expressão excessivamente profunda")
    if isinstance(expr, Numero):
        return Polinomio.constante(expr.valor)
    if isinstance(expr, Variavel):
        return Polinomio.variavel(expr.nome)
    if isinstance(expr, Unario) and expr.operador == "-":
        return -normalizar(expr.argumento, nivel + 1)
    if isinstance(expr, Binario):
        a = normalizar(expr.esquerda, nivel + 1)
        b = normalizar(expr.direita, nivel + 1)
        if expr.operador == "+":
            return a + b
        if expr.operador == "-":
            return a - b
        if expr.operador == "*":
            return a * b
        if expr.operador == "/":
            divisor = b.constante_pura()
            if not divisor:
                raise ErroOmega("Divisão por zero")
            return a * Polinomio.constante(Fraction(1, 1) / divisor)
        if expr.operador == "^":
            exp = b.constante_pura()
            if exp.denominator != 1:
                raise ErroOmega("Expoente fracionário ainda não é suportado")
            return a.potencia(int(exp))
    raise ErroOmega("Expressão não suportada pela álgebra polinomial")
