"""Verificação estática e dimensional da linguagem Ômega 0.4.

As dimensões de vetores e matrizes são conhecidas durante a análise.
Esta é uma checagem de *formas* estáticas, não tipos dependentes formais.
"""
from __future__ import annotations

from dataclasses import dataclass

from .algebra import normalizar
from .sintaxe import Binario, Comando, ErroOmega, Expressao, Numero, Unario, Variavel
from .tensores import conferir_limites, expandir, formato, tipo_tensor, visitar_escalas
from .parametros_tensor import coordenadas, em_ast, folhas


@dataclass(frozen=True)
class ResultadoTipos:
    simbolos: dict[str, str]
    tipos_comandos: tuple[str, ...]


def variaveis_ast(expr: Expressao, nivel: int = 0) -> set[str]:
    """Examina os nomes originais, sem descartar variáveis canceladas."""
    if nivel > 200:
        raise ErroOmega("Expressão excessivamente profunda")
    if isinstance(expr, Numero):
        return set()
    if isinstance(expr, Variavel):
        return {expr.nome}
    if isinstance(expr, Unario):
        return variaveis_ast(expr.argumento, nivel + 1)
    if isinstance(expr, Binario):
        return variaveis_ast(expr.esquerda, nivel+1) | variaveis_ast(expr.direita, nivel+1)
    raise ErroOmega('Esperada expressão escalar expandida')


def exigir_nome(tabela: dict[str, str], nome: str, esperado: str) -> None:
    obtido = tabela.get(nome)
    if obtido != esperado:
        raise ErroOmega(f"'{nome}' não declarado; esperado {esperado}") if obtido is None else ErroOmega(f"'{nome}' tem tipo {obtido}; esperado {esperado}")


def checar_expressao(expr: Expressao, tabela: dict[str, str], internas: set[str] | None = None) -> None:
    for nome in sorted(variaveis_ast(expr)):
        if nome not in (internas or set()):
            exigir_nome(tabela, nome, 'Parametro')
    normalizar(expr)


def checar_tipos(comandos: list[Comando]) -> ResultadoTipos:
    """Rejeita o programa antes de executar a primeira mutação."""
    tabela: dict[str, str] = {}
    tensores: dict[str, Expressao] = {}
    internas: set[str] = set()
    descricoes: list[str] = []
    for i, c in enumerate(comandos, 1):
        try:
            tipo = c.tipo
            if tipo in {'parametro', 'parametro_tensor', 'perda', 'teorema', 'vetor', 'matriz', 'tensor'}:
                if not c.nome or c.nome in tabela:
                    raise ErroOmega(f"Identificador já declarado ou inválido: {c.nome!r}")
            if tipo == 'parametro':
                if c.expressao is None:
                    raise ErroOmega('Comando sem expressão')
                checar_expressao(c.expressao, tabela)
                tabela[c.nome] = 'Parametro'
                descricoes.append('Escalar → Parametro')
            elif tipo == 'parametro_tensor':
                if c.expressao is None or c.parametro not in ('vetor', 'matriz'):
                    raise ErroOmega('Parâmetro tensorial sem forma ou inicializador')
                valor = conferir_limites(expandir(c.expressao, tensores))
                dims = formato(valor)
                dimensao_esperada = 1 if c.parametro == 'vetor' else 2
                if len(dims) != dimensao_esperada:
                    raise ErroOmega(f'parametro {c.parametro} exige tensor de dimensão {dimensao_esperada}')
                visitar_escalas(valor, lambda x: checar_expressao(x, tabela, internas))
                mapa = coordenadas(c.nome, dims)
                nomes = set(folhas(mapa))
                if nomes & internas or nomes & set(tabela):
                    raise ErroOmega('Colisão de nomes internos')
                internas.update(nomes)
                tensores[c.nome] = em_ast(mapa)
                tabela[c.nome] = f'Parametro{tipo_tensor(valor)}'
                descricoes.append(f'{tipo_tensor(valor)} → {tabela[c.nome]}')
            elif tipo in {'vetor', 'matriz', 'tensor'}:
                if c.expressao is None:
                    raise ErroOmega('Declaração tensorial sem expressão')
                v = conferir_limites(expandir(c.expressao, tensores))
                dims = formato(v)
                if not dims:
                    raise ErroOmega('tensor, vetor e matriz exigem ao menos uma dimensão')
                if tipo == 'vetor' and len(dims) != 1:
                    raise ErroOmega('vetor exige uma expressão de dimensão 1')
                if tipo == 'matriz' and len(dims) != 2:
                    raise ErroOmega('matriz exige uma expressão de dimensão 2')
                visitar_escalas(v, lambda x: checar_expressao(x, tabela, internas))
                tabela[c.nome] = tipo_tensor(v)
                tensores[c.nome] = c.expressao
                descricoes.append(tabela[c.nome])
            elif tipo in {'perda', 'reescrever'}:
                if tipo == 'reescrever':
                    exigir_nome(tabela, c.nome, 'Polinomio')
                if c.expressao is None:
                    raise ErroOmega('Comando sem expressão')
                valor = conferir_limites(expandir(c.expressao, tensores))
                if formato(valor):
                    raise ErroOmega(f'Perda precisa ser Escalar, não {tipo_tensor(valor)}')
                checar_expressao(valor, tabela, internas)
                if tipo == 'perda':
                    tabela[c.nome] = 'Polinomio'
                descricoes.append('Polinomio' if tipo == 'perda' else 'Polinomio → Polinomio')
            elif tipo in {'gradiente', 'gradientes', 'passo'}:
                exigir_nome(tabela, c.nome, 'Polinomio')
                if tipo != 'gradientes':
                    tipo_p = tabela.get(c.parametro)
                    if tipo_p != 'Parametro' and not (isinstance(tipo_p, str) and tipo_p.startswith('ParametroVetor[') or isinstance(tipo_p, str) and tipo_p.startswith('ParametroMatriz[')):
                        exigir_nome(tabela, c.parametro, 'Parametro')
                if tipo == 'passo':
                    if c.taxa is None:
                        raise ErroOmega('Passo sem taxa')
                    valor = conferir_limites(expandir(c.taxa, tensores))
                    if formato(valor):
                        raise ErroOmega('Taxa deve ser Escalar')
                    checar_expressao(valor, tabela, internas)
                    descricoes.append(('Parametro tensorial × ' if c.parametro in tensores and c.parametro in {k for k in tensores if tabela[k].startswith('Parametro')} else 'Parametro escalar × ') + 'Taxa escalar → Prova')
                elif tipo == 'gradiente':
                    desc = tabela[c.parametro]
                    descricoes.append(f'Polinomio × {desc} → {desc[9:] if desc.startswith("ParametroVetor") or desc.startswith("ParametroMatriz") else "Escalar"}')
                else:
                    descricoes.append('Polinomio → GradienteReverso')
            elif tipo in {'provar', 'teorema'}:
                if c.expressao is None or c.direita is None:
                    raise ErroOmega('Igualdade incompleta')
                a = conferir_limites(expandir(c.expressao, tensores))
                b = conferir_limites(expandir(c.direita, tensores))
                if formato(a) != formato(b):
                    raise ErroOmega('Prova exige mesma dimensão dos dois lados')
                visitar_escalas(a, normalizar)
                visitar_escalas(b, normalizar)
                if tipo == 'teorema':
                    tabela[c.nome] = 'Prova'
                descricoes.append(f'{tipo_tensor(a)} == {tipo_tensor(b)} → Prova')
            elif tipo == 'verificar':
                exigir_nome(tabela, c.nome, 'Prova')
                descricoes.append('Prova → Prova')
            elif tipo == 'mostrar':
                if c.nome not in tabela:
                    raise ErroOmega(f'Identificador não declarado: {c.nome!r}')
                descricoes.append(f'{tabela[c.nome]} → Saida')
            else:
                raise ErroOmega(f'Comando desconhecido: {tipo}')
        except ErroOmega as erro:
            raise ErroOmega(f'Erro de tipo no comando {i} ({c.tipo}): {erro}') from erro
    return ResultadoTipos(dict(tabela), tuple(descricoes))
