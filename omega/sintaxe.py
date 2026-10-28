"""Analisador léxico e sintático da linguagem Ômega 0.4.

Não usa eval/exec nem repassa o código Ômega ao interpretador Python.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Union


class ErroOmega(Exception):
    """Erro de sintaxe, verificação ou execução em Ômega."""


@dataclass(frozen=True)
class Numero:
    valor: Fraction


@dataclass(frozen=True)
class Variavel:
    nome: str


@dataclass(frozen=True)
class Unario:
    operador: str
    argumento: "Expressao"


@dataclass(frozen=True)
class Binario:
    operador: str
    esquerda: "Expressao"
    direita: "Expressao"


@dataclass(frozen=True)
class Lista:
    elementos: tuple["Expressao", ...]


@dataclass(frozen=True)
class Chamada:
    funcao: str
    argumentos: tuple["Expressao", ...]


Expressao = Union[Numero, Variavel, Unario, Binario, Lista, Chamada]


@dataclass(frozen=True)
class Comando:
    tipo: str
    nome: str = ""
    expressao: Expressao | None = None
    direita: Expressao | None = None
    parametro: str = ""
    taxa: Expressao | None = None
    semente: int | None = None


@dataclass(frozen=True)
class Token:
    tipo: str
    texto: str
    linha: int
    coluna: int


_RE_TOKEN = re.compile(r"(?P<ESPACO>\s+)|(?P<COMENTARIO>\#[^\n]*|//[^\n]*)|"
                       r"(?P<NUMERO>\d+(?:\.\d+)?)|"
                       r"(?P<NOME>[^\W\d]\w*)|"
                       r"(?P<SIMBOLO>==|[+*/^=();,\[\]@-])|"
                       r"(?P<INVALIDO>.)", re.UNICODE)


def tokenizar(fonte: str) -> list[Token]:
    """Converte texto em tokens com localização para mensagens de erro."""
    linha, coluna = 1, 1
    saida = []
    for achado in _RE_TOKEN.finditer(fonte):
        categoria = achado.lastgroup
        texto = achado.group()
        if categoria == "INVALIDO":
            raise ErroOmega(f"Caractere inesperado {texto!r} na linha {linha}, coluna {coluna}")
        if categoria not in ("ESPACO", "COMENTARIO"):
            saida.append(Token(categoria or "", texto, linha, coluna))
        if "\n" in texto:
            linha += texto.count("\n")
            coluna = len(texto.rsplit("\n", 1)[-1]) + 1
        else:
            coluna += len(texto)
    saida.append(Token("FIM", "<fim>", linha, coluna))
    return saida


ALIAS = {
    "parametro": "parametro", "param": "parametro",
    "perda": "perda", "loss": "perda",
    "gradiente": "gradiente", "grad": "gradiente",
    "passo": "passo", "step": "passo",
    "provar": "provar", "prove": "provar",
    "reescrever": "reescrever", "rewrite": "reescrever",
    "mostrar": "mostrar", "show": "mostrar",
    "teorema": "teorema", "theorem": "teorema",
    "verificar": "verificar", "verify": "verificar",
    "vetor": "vetor", "vector": "vetor",
    "matriz": "matriz", "matrix": "matriz",
    "tensor": "tensor", "gradientes": "gradientes", "grads": "gradientes",
    "em": "em", "wrt": "em", "taxa": "taxa", "rate": "taxa",
    "passo_livre": "passo_livre", "passo_ruidoso": "passo_ruidoso",
    "semente": "semente",
}


class Analisador:
    """Parser descendente. A exponenciação tem prioridade sobre o sinal unário."""

    def __init__(self, fonte: str):
        self.tokens = tokenizar(fonte)
        self.indice = 0

    @property
    def atual(self) -> Token:
        return self.tokens[self.indice]

    def aceitar(self, texto: str) -> bool:
        if self.atual.texto == texto:
            self.indice += 1
            return True
        return False

    def exigir(self, texto: str) -> None:
        if not self.aceitar(texto):
            self.erro(f"Esperado {texto!r}")

    def erro(self, mensagem: str) -> None:
        t = self.atual
        raise ErroOmega(f"{mensagem}; encontrado {t.texto!r} (linha {t.linha}, coluna {t.coluna})")

    def nome(self) -> str:
        if self.atual.tipo != "NOME" or self.atual.texto in ALIAS or self.atual.texto.startswith("__omega_coord_"):
            self.erro("Esperado identificador não reservado")
        resposta = self.atual.texto
        self.indice += 1
        return resposta

    def palavra(self, palavra: str) -> None:
        if ALIAS.get(self.atual.texto) != palavra:
            self.erro(f"Esperado palavra-chave {palavra!r}")
        self.indice += 1

    def programa(self) -> list[Comando]:
        resultado = []
        while self.atual.tipo != "FIM":
            resultado.append(self.comando())
        return resultado

    def comando(self) -> Comando:
        inicio = ALIAS.get(self.atual.texto)
        self.indice += 1 if inicio else 0
        if inicio == "parametro" and ALIAS.get(self.atual.texto) in ("vetor", "matriz"):
            categoria = ALIAS[self.atual.texto]
            self.indice += 1
            nome = self.nome()
            self.exigir("=")
            expr = self.expressao()
            self.exigir(";")
            return Comando("parametro_tensor", nome=nome, parametro=categoria, expressao=expr)
        if inicio in ("parametro", "perda", "reescrever", "vetor", "matriz", "tensor"):
            nome = self.nome()
            self.exigir("=")
            expr = self.expressao()
            self.exigir(";")
            return Comando(inicio, nome=nome, expressao=expr)
        if inicio in ("gradiente", "passo", "passo_livre", "passo_ruidoso"):
            alvo = self.nome()
            self.palavra("em")
            parametro = self.nome()
            taxa = None
            semente = None
            if inicio != "gradiente":
                self.palavra("taxa")
                taxa = self.expressao()
                if inicio == "passo_ruidoso":
                    self.palavra("semente")
                    if self.atual.tipo != "NUMERO" or not self.atual.texto.isdigit():
                        self.erro("Semente precisa ser inteiro não negativo")
                    semente = int(self.atual.texto)
                    self.indice += 1
            self.exigir(";")
            return Comando(inicio, nome=alvo, parametro=parametro, taxa=taxa, semente=semente)
        if inicio == "teorema":
            nome = self.nome()
            self.exigir("=")
            esquerda = self.expressao()
            self.exigir("==")
            direita = self.expressao()
            self.exigir(";")
            return Comando(inicio, nome=nome, expressao=esquerda, direita=direita)
        if inicio == "gradientes":
            nome = self.nome()
            self.exigir(";")
            return Comando(inicio, nome=nome)
        if inicio == "verificar":
            nome = self.nome()
            self.exigir(";")
            return Comando(inicio, nome=nome)
        if inicio == "provar":
            esquerda = self.expressao()
            self.exigir("==")
            direita = self.expressao()
            self.exigir(";")
            return Comando(inicio, expressao=esquerda, direita=direita)
        if inicio == "mostrar":
            nome = self.nome()
            self.exigir(";")
            return Comando(inicio, nome=nome)
        self.erro("Comando desconhecido")

    def expressao(self) -> Expressao:
        expr = self.termo()
        while self.atual.texto in ("+", "-"):
            op = self.atual.texto
            self.indice += 1
            expr = Binario(op, expr, self.termo())
        return expr

    def termo(self) -> Expressao:
        expr = self.unario()
        while self.atual.texto in ("*", "/", "@"):
            op = self.atual.texto
            self.indice += 1
            expr = Binario(op, expr, self.unario())
        return expr

    def unario(self) -> Expressao:
        if self.aceitar("-"):
            return Unario("-", self.unario())
        if self.aceitar("+"):
            return self.unario()
        return self.potencia()

    def potencia(self) -> Expressao:
        expr = self.atomo()
        if self.aceitar("^"):
            expr = Binario("^", expr, self.unario())
        return expr

    def atomo(self) -> Expressao:
        atual = self.atual
        if atual.tipo == "NUMERO":
            self.indice += 1
            return Numero(Fraction(atual.texto))
        if atual.tipo == "NOME" and atual.texto not in ALIAS and not atual.texto.startswith("__omega_coord_"):
            self.indice += 1
            if self.aceitar("("):
                args = []
                if not self.aceitar(")"):
                    args.append(self.expressao())
                    while self.aceitar(","):
                        args.append(self.expressao())
                    self.exigir(")")
                return Chamada(atual.texto, tuple(args))
            return Variavel(atual.texto)
        if self.aceitar("["):
            itens = []
            if not self.aceitar("]"):
                itens.append(self.expressao())
                while self.aceitar(","):
                    itens.append(self.expressao())
                self.exigir("]")
            return Lista(tuple(itens))
        if self.aceitar("("):
            expr = self.expressao()
            self.exigir(")")
            return expr
        self.erro("Esperada expressão numérica, variável ou parêntese")


def analisar(fonte: str) -> list[Comando]:
    return Analisador(fonte).programa()


def expressao_para_dict(e: Expressao) -> dict:
    if isinstance(e, Numero):
        return {"tipo": "num", "valor": str(e.valor)}
    if isinstance(e, Variavel):
        return {"tipo": "var", "nome": e.nome}
    if isinstance(e, Unario):
        return {"tipo": "un", "op": e.operador, "arg": expressao_para_dict(e.argumento)}
    if isinstance(e, Lista):
        return {"tipo": "lista", "itens": [expressao_para_dict(x) for x in e.elementos]}
    if isinstance(e, Chamada):
        return {"tipo": "chamada", "funcao": e.funcao,
                "args": [expressao_para_dict(x) for x in e.argumentos]}
    if isinstance(e, Binario):
        return {"tipo": "bin", "op": e.operador,
                "esq": expressao_para_dict(e.esquerda),
                "dir": expressao_para_dict(e.direita)}
    raise ErroOmega("Expressão desconhecida")


def expressao_de_dict(d: dict, nivel: int = 0) -> Expressao:
    """Reconstitui AST verificando estrutura e operações (não executa código JSON)."""
    if nivel > 200 or not isinstance(d, dict):
        raise ErroOmega("AST inválida ou excessivamente profunda")
    try:
        tipo = d["tipo"]
        if tipo == "num":
            valor = Fraction(d["valor"])
            return Numero(valor)
        if tipo == "var":
            nome = d["nome"]
            if not isinstance(nome, str) or not nome.isidentifier() or nome in ALIAS or nome.startswith("__omega_coord_"):
                raise ErroOmega("Nome de variável inválido no AST")
            return Variavel(nome)
        if tipo == "un" and d["op"] == "-":
            return Unario("-", expressao_de_dict(d["arg"], nivel + 1))
        if tipo == "lista" and isinstance(d.get("itens"), list) and len(d["itens"]) <= 128:
            return Lista(tuple(expressao_de_dict(x, nivel + 1) for x in d["itens"]))
        if tipo == "chamada" and d.get("funcao") in ("dot", "transposta", "relu", "soma", "zeros", "identidade") and isinstance(d.get("args"), list) and len(d["args"]) <= 3:
            return Chamada(d["funcao"], tuple(expressao_de_dict(x, nivel + 1) for x in d["args"]))
        if tipo == "bin" and d["op"] in ("+", "-", "*", "/", "^", "@"):
            return Binario(d["op"], expressao_de_dict(d["esq"], nivel + 1),
                           expressao_de_dict(d["dir"], nivel + 1))
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as erro:
        raise ErroOmega(f"AST inválida: {erro}") from erro
    raise ErroOmega("Tipo ou operador de AST desconhecido")


def comando_para_dict(c: Comando) -> dict:
    d = {"tipo": c.tipo, "nome": c.nome, "parametro": c.parametro}
    if c.expressao is not None:
        d["expressao"] = expressao_para_dict(c.expressao)
    if c.direita is not None:
        d["direita"] = expressao_para_dict(c.direita)
    if c.taxa is not None:
        d["taxa"] = expressao_para_dict(c.taxa)
    if c.semente is not None:
        d["semente"] = c.semente
    return d


def comando_de_dict(d: dict) -> Comando:
    if not isinstance(d, dict):
        raise ErroOmega("Comando do arquivo compilado não é um objeto")
    tipo = d.get("tipo")
    if tipo not in {"parametro", "parametro_tensor", "perda", "reescrever", "gradiente", "gradientes", "passo", "passo_livre", "passo_ruidoso", "provar", "mostrar", "teorema", "verificar", "vetor", "matriz", "tensor"}:
        raise ErroOmega(f"Comando compilado desconhecido: {tipo!r}")
    try:
        nome = d.get("nome", "")
        parametro = d.get("parametro", "")
        def identificador_valido(x):
            return isinstance(x, str) and (not x or (x.isidentifier() and
                   x not in ALIAS and not x.startswith("__omega_coord_")))
        if not identificador_valido(nome) or (
            tipo != "parametro_tensor" and not identificador_valido(parametro)
        ):
            raise ErroOmega("Identificador inválido no comando compilado")
        expr = expressao_de_dict(d["expressao"]) if "expressao" in d else None
        direita = expressao_de_dict(d["direita"]) if "direita" in d else None
        taxa = expressao_de_dict(d["taxa"]) if "taxa" in d else None
        if tipo in ("parametro", "parametro_tensor", "perda", "reescrever", "vetor", "matriz", "tensor") and (not nome or expr is None):
            raise ErroOmega("Comando compilado sem nome ou expressão")
        if tipo in ("provar", "teorema") and (expr is None or direita is None):
            raise ErroOmega("Prova compilada incompleta")
        if tipo in ("gradiente", "passo", "passo_livre", "passo_ruidoso") and (not nome or not parametro):
            raise ErroOmega("Gradiente/passo sem identificadores")
        if tipo == "parametro_tensor" and parametro not in ("vetor", "matriz"):
            raise ErroOmega("Parâmetro tensorial sem categoria válida")
        if tipo in ("passo", "passo_livre", "passo_ruidoso") and taxa is None:
            raise ErroOmega("Passo sem taxa")
        if tipo in ("teorema", "verificar", "gradientes") and not nome:
            raise ErroOmega("Comando de teorema sem identificador")
        if tipo == "mostrar" and not nome:
            raise ErroOmega("Mostrar sem identificador")
        semente = d.get("semente")
        if semente is not None and (type(semente) is not int or not 0 <= semente < 2**32):
            raise ErroOmega("Semente inválida")
        if tipo == "passo_ruidoso" and semente is None:
            raise ErroOmega("Passo ruidoso sem semente")
        return Comando(tipo, nome, expr, direita, parametro, taxa, semente)
    except (KeyError, TypeError, ValueError) as erro:
        raise ErroOmega(f"Comando compilado inválido: {erro}") from erro
