"""Núcleo de verificação Ômega 0.4.

Não importa o executor nem omega.algebra. Usa somente AST serializada, frações
exatas e operações próprias. É um verificador pequeno, NÃO uma prova de que
seu código Python é correto.
"""
from __future__ import annotations

from fractions import Fraction

MONOMIOS_MAX = 5000
EXPOENTE_MAX = 20
PROFUNDIDADE_MAX = 120

# Um monômio é uma tupla de pares (variável, potência), em ordem alfabética.
# Um polinômio é um mapa de monômios para coeficientes racionais diferentes de zero.


class ProvaInvalida(Exception):
    pass


def numero(x: object) -> Fraction:
    if not isinstance(x, str) or len(x) > 10000:
        raise ProvaInvalida("Número deve ser texto racional limitado")
    try:
        return Fraction(x)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as erro:
        raise ProvaInvalida("Número racional inválido") from erro


def limpar(poly: dict) -> dict:
    limpo = {m: c for m, c in poly.items() if c}
    if len(limpo) > MONOMIOS_MAX:
        raise ProvaInvalida("Limite de monômios excedido")
    return limpo


def soma(a: dict, b: dict, fator: int = 1) -> dict:
    out = dict(a)
    for monomio, coeficiente in b.items():
        out[monomio] = out.get(monomio, Fraction(0)) + fator * coeficiente
    return limpar(out)


def produto(a: dict, b: dict) -> dict:
    out: dict = {}
    for ma, ca in a.items():
        for mb, cb in b.items():
            graus = dict(ma)
            for nome, grau in mb:
                graus[nome] = graus.get(nome, 0) + grau
            monomio = tuple(sorted(graus.items()))
            out[monomio] = out.get(monomio, Fraction(0)) + ca * cb
            if len(out) > MONOMIOS_MAX * 2:
                raise ProvaInvalida("Produto grande demais")
    return limpar(out)


def potencia(p: dict, n: int) -> dict:
    if not 0 <= n <= EXPOENTE_MAX:
        raise ProvaInvalida("Expoente fora do intervalo 0..20")
    resultado = {(): Fraction(1)}
    # Algoritmo independente da exponenciação binária usada pelo executor.
    for _ in range(n):
        resultado = produto(resultado, p)
    return resultado


def polinomio(ast: object, nivel: int = 0) -> dict:
    if not isinstance(ast, dict) or nivel > PROFUNDIDADE_MAX:
        raise ProvaInvalida("AST inválida ou profunda demais")
    tipo = ast.get("tipo")
    if tipo == "num":
        return limpar({(): numero(ast.get("valor"))})
    if tipo == "var":
        nome = ast.get("nome")
        if not isinstance(nome, str) or not nome.isidentifier():
            raise ProvaInvalida("Variável inválida")
        return {((nome, 1),): Fraction(1)}
    if tipo == "un" and ast.get("op") == "-":
        p = polinomio(ast.get("arg"), nivel + 1)
        return {m: -c for m, c in p.items()}
    if tipo != "bin" or ast.get("op") not in {"+", "-", "*", "/", "^"}:
        raise ProvaInvalida("Operador ou nó desconhecido")
    a = polinomio(ast.get("esq"), nivel + 1)
    b = polinomio(ast.get("dir"), nivel + 1)
    op = ast["op"]
    if op == "+":
        return soma(a, b)
    if op == "-":
        return soma(a, b, -1)
    if op == "*":
        return produto(a, b)
    if any(m != () for m in b):
        raise ProvaInvalida("Divisão ou expoente não constante")
    constante = b.get((), Fraction(0))
    if op == "/":
        if constante == 0:
            raise ProvaInvalida("Divisão por zero")
        return limpar({m: c / constante for m, c in a.items()})
    if constante.denominator != 1:
        raise ProvaInvalida("Expoente não inteiro")
    return potencia(a, int(constante))


def forma_normal(p: dict) -> list[dict]:
    return [{"monomio": [[nome, grau] for nome, grau in monomio],
             "coeficiente": str(coef)} for monomio, coef in sorted(p.items())]


def derivada(p: dict, variavel: str) -> dict:
    out: dict = {}
    for monomio, coef in p.items():
        expoentes = dict(monomio)
        grau = expoentes.get(variavel, 0)
        if grau == 0:
            continue
        if grau == 1:
            del expoentes[variavel]
        else:
            expoentes[variavel] = grau - 1
        novo = tuple(sorted(expoentes.items()))
        out[novo] = out.get(novo, Fraction(0)) + grau * coef
    return limpar(out)


def avaliar(p: dict, estado: dict[str, Fraction]) -> Fraction:
    total = Fraction(0)
    for monomio, coef in p.items():
        termo = coef
        for nome, grau in monomio:
            if nome not in estado:
                raise ProvaInvalida(f"Variável {nome!r} ausente do estado")
            termo *= estado[nome] ** grau
        total += termo
    return total


def ler_estado(dados: object) -> dict[str, Fraction]:
    if not isinstance(dados, dict):
        raise ProvaInvalida("Estado inválido")
    estado = {}
    for nome, valor in dados.items():
        if not isinstance(nome, str) or not nome.isidentifier():
            raise ProvaInvalida("Nome inválido no estado")
        estado[nome] = numero(valor)
    return estado


def validar_certificado(cert: object) -> bool:
    """Só retorna True depois de recalcular as alegações do certificado."""
    try:
        if not isinstance(cert, dict):
            return False
        tipo = cert.get("tipo")
        if tipo == "expansao_tensor":
            from .nucleo_tensor import validar_expansao
            return validar_expansao(cert)
        if tipo == "identidade_tensorial":
            from .nucleo_tensor import validar_identidade_tensorial
            return validar_identidade_tensorial(cert)
        if tipo == "gradiente_tensor":
            from .nucleo_parametros import validar_gradiente_tensor
            return validar_gradiente_tensor(cert)
        if tipo == "passo_tensor":
            from .nucleo_parametros import validar_passo_tensor
            return validar_passo_tensor(cert)
        if tipo == "retropropagacao":
            p = polinomio(cert["expressao"])
            estado = ler_estado(cert["estado"])
            resultados = cert["resultados"]
            return (isinstance(resultados, dict) and
                    set(resultados) == set(estado) and
                    all(isinstance(resultados[x], str) and
                        resultados[x] == str(avaliar(derivada(p, x), estado))
                        for x in estado))
        if tipo in ("identidade", "reescrita"):
            a = polinomio(cert["esquerda"])
            b = polinomio(cert["direita"])
            return a == b and cert["forma_normal"] == forma_normal(a)
        if tipo == "gradiente":
            p = polinomio(cert["expressao"])
            estado = ler_estado(cert["estado"])
            x = cert["parametro"]
            if not isinstance(x, str) or x not in estado:
                return False
            return str(avaliar(derivada(p, x), estado)) == cert["resultado"]
        if tipo == "passo":
            p = polinomio(cert["expressao"])
            t = polinomio(cert["expressao_taxa"])
            antes = ler_estado(cert["estado_antes"])
            depois = ler_estado(cert["estado_depois"])
            x = cert["parametro"]
            if not isinstance(x, str) or x not in antes or set(antes) != set(depois):
                return False
            taxa = avaliar(t, antes)
            gradiente = avaliar(derivada(p, x), antes)
            if taxa <= 0 or str(taxa) != cert["taxa"] or str(gradiente) != cert["gradiente"]:
                return False
            esperado = dict(antes)
            esperado[x] = antes[x] - taxa * gradiente
            if esperado != depois:
                return False
            perda_antes = avaliar(p, antes)
            perda_depois = avaliar(p, depois)
            return (perda_depois <= perda_antes and
                    str(perda_antes) == cert["perda_antes"] and
                    str(perda_depois) == cert["perda_depois"])
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError,
            RecursionError, ProvaInvalida, ZeroDivisionError):
        return False
    return False
