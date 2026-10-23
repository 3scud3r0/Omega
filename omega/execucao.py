"""Máquina de execução Ômega; certificados checados por um núcleo isolado."""
from __future__ import annotations

from fractions import Fraction
from .algebra import Polinomio, normalizar
from .autodiff import retropropagar
from .autodiff_tensor import retropropagar_tensores
from .parametros_tensor import coordenadas, em_ast, folhas, remodelar, como_listas
from .tensores import conferir_limites, expandir, formato, para_ast, tipo_tensor
from .nucleo import validar_certificado as verificar_certificado
from .tipos import checar_tipos
from .sintaxe import (
    Binario, Chamada, Lista, Unario, Comando, ErroOmega, Expressao,
    expressao_de_dict, expressao_para_dict,
)


def usa_tensor(expr: Expressao) -> bool:
    if isinstance(expr, (Lista, Chamada)):
        return True
    if isinstance(expr, Unario):
        return usa_tensor(expr.argumento)
    if isinstance(expr, Binario):
        return expr.operador == '@' or usa_tensor(expr.esquerda) or usa_tensor(expr.direita)
    return False



def ler_estado(dados: dict) -> dict[str, Fraction]:
    if not isinstance(dados, dict):
        raise ErroOmega("Estado do certificado deve ser um objeto JSON")
    estado = {}
    for nome, valor in dados.items():
        if not isinstance(nome, str) or not nome.isidentifier():
            raise ErroOmega("Parâmetro inválido no certificado")
        try:
            estado[nome] = Fraction(valor)
        except (TypeError, ValueError, ZeroDivisionError) as erro:
            raise ErroOmega("Número inválido no certificado") from erro
    return estado


def serializar_estado(estado: dict[str, Fraction]) -> dict[str, str]:
    return {nome: str(valor) for nome, valor in sorted(estado.items())}




class MaquinaOmega:
    def __init__(self):
        self.parametros: dict[str, Fraction] = {}
        self.perdas: dict[str, Expressao] = {}
        self.teoremas: dict[str, dict] = {}
        self.tensores: dict[str, Expressao] = {}
        self.parametros_tensoriais: dict[str, tuple] = {}
        self.perdas_originais: dict[str, Expressao] = {}
        self.saidas: list[str] = []
        self.certificados: list[dict] = []

    def avaliar(self, expr: Expressao) -> Fraction:
        return normalizar(expr).avaliar(self.parametros)

    def validar_variaveis(self, expr: Expressao) -> Polinomio:
        p = normalizar(expr)
        ausentes = p.variaveis() - set(self.parametros)
        if ausentes:
            raise ErroOmega(f"Parâmetro(s) não declarado(s): {', '.join(sorted(ausentes))}")
        return p

    def perda(self, nome: str) -> tuple[Expressao, Polinomio]:
        if nome not in self.perdas:
            raise ErroOmega(f"Perda não declarada: {nome}")
        expr = self.perdas[nome]
        return expr, self.validar_variaveis(expr)

    def expansao_com_prova(self, original: Expressao):
        """Expande e exige um certificado independente da regra tensorial."""
        valor = conferir_limites(expandir(original, self.tensores))
        expandido = para_ast(valor)
        # No certificado, as definições ficam expressas na sintaxe original.
        defs = {nome: expressao_para_dict(e) for nome, e in self.tensores.items()}
        def canon(x):
            if isinstance(x, tuple):
                return [canon(y) for y in x]
            return normalizar(x).forma_normal()
        cert = {
            'tipo': 'expansao_tensor',
            'original': expressao_para_dict(original),
            'definicoes': defs,
            'expandido': expressao_para_dict(expandido),
            'dimensoes': list(formato(valor)),
            'formas': canon(valor),
        }
        self.guardar(cert)
        return valor

    def guardar(self, cert: dict) -> None:
        # Defesa adicional: até o executor precisa passar pelo verificador.
        if not verificar_certificado(cert):
            raise ErroOmega("Falha interna: certificado matemático rejeitado")
        self.certificados.append(cert)

    def executar(self, comandos: list[Comando]) -> "MaquinaOmega":
        checar_tipos(comandos)  # Verifica programa INTEIRO antes de qualquer mutação.
        for indice, c in enumerate(comandos, 1):
            try:
                self.executar_um(c)
            except ErroOmega as erro:
                raise ErroOmega(f"Comando {indice} ({c.tipo}): {erro}") from erro
        return self

    def executar_um(self, c: Comando) -> None:
        if c.tipo == 'parametro_tensor':
            if c.expressao is None:
                raise ErroOmega('Parâmetro tensorial sem inicializador')
            inicial = conferir_limites(expandir(c.expressao, self.tensores))
            dims = formato(inicial)
            if len(dims) != (1 if c.parametro == 'vetor' else 2):
                raise ErroOmega('Dimensões erradas para parâmetro tensorial')
            nomes = coordenadas(c.nome, dims)
            from .tensores import visitar_escalas
            expressoes = []
            visitar_escalas(inicial, expressoes.append)
            valores = [self.validar_variaveis(x).avaliar(self.parametros) for x in expressoes]
            for nome, val in zip(folhas(nomes), valores):
                if nome in self.parametros:
                    raise ErroOmega('Colisão entre parâmetros internos')
                self.parametros[nome] = val
            self.parametros_tensoriais[c.nome] = nomes
            self.tensores[c.nome] = em_ast(nomes)
            self.saidas.append(f'parâmetro {c.nome}: {tipo_tensor(inicial)} = '
                               f'{como_listas(remodelar(nomes, self.parametros))}')
            return
        if c.tipo in {'vetor', 'matriz', 'tensor'}:
            if c.expressao is None:
                raise ErroOmega('Tensor sem expressão')
            valor = self.expansao_com_prova(c.expressao)
            self.tensores[c.nome] = c.expressao
            self.saidas.append(f'{c.tipo} {c.nome}: {tipo_tensor(valor)}')
            return

        if c.tipo == "gradientes":
            expr, p = self.perda(c.nome)
            if self.tensores:
                grads = retropropagar_tensores(self.perdas_originais.get(c.nome, expr),
                                                self.tensores, self.parametros)
            else:
                grads = retropropagar(expr, self.parametros)
            self.guardar({'tipo': 'retropropagacao', 'expressao': expressao_para_dict(expr),
                          'estado': serializar_estado(self.parametros),
                          'resultados': serializar_estado(grads)})
            internos = {n for mapa in self.parametros_tensoriais.values() for n in folhas(mapa)}
            for nome, valor in sorted(grads.items()):
                if nome not in internos:
                    self.saidas.append(f'd({c.nome})/d({nome}) [reverso] = {valor}')
            for nome, mapa in sorted(self.parametros_tensoriais.items()):
                self.saidas.append(f'd({c.nome})/d({nome}) [reverso tensorial] = '
                                   f'{como_listas(remodelar(mapa, grads))}')
            return

        if c.tipo == "parametro":
            if c.nome in self.parametros or c.nome in self.perdas or c.nome in self.teoremas:
                raise ErroOmega(f"Identificador já declarado: {c.nome}")
            if c.expressao is None:
                raise ErroOmega("Faltando valor do parâmetro")
            valor = self.validar_variaveis(c.expressao).avaliar(self.parametros)
            self.parametros[c.nome] = valor
            self.saidas.append(f"parâmetro {c.nome} = {valor}")
            return

        if c.tipo == "perda":
            if c.nome in self.parametros or c.nome in self.perdas or c.nome in self.teoremas:
                raise ErroOmega(f"Identificador já declarado: {c.nome}")
            if c.expressao is None:
                raise ErroOmega("Faltando expressão da perda")
            valor = self.expansao_com_prova(c.expressao) if self.tensores or usa_tensor(c.expressao) else expandir(c.expressao, {})
            if formato(valor):
                raise ErroOmega('A perda precisa ser escalar')
            expandido = para_ast(valor)
            p = self.validar_variaveis(expandido)
            self.perdas[c.nome] = expandido
            self.perdas_originais[c.nome] = c.expressao
            self.saidas.append(f"perda {c.nome} = {p.avaliar(self.parametros)}")
            return

        if c.tipo == "mostrar":
            if c.nome in self.tensores:
                valor = conferir_limites(expandir(self.tensores[c.nome], self.tensores))
                def aval(x):
                    if isinstance(x,tuple):
                        return [aval(y) for y in x]
                    return str(self.validar_variaveis(x).avaliar(self.parametros))
                self.saidas.append(f'{c.nome} = {aval(valor)}')
                return
            if c.nome in self.parametros:
                self.saidas.append(f"{c.nome} = {self.parametros[c.nome]}")
                return
            if c.nome in self.perdas:
                _, p = self.perda(c.nome)
                self.saidas.append(f"{c.nome} = {p.avaliar(self.parametros)}")
                return
            if c.nome in self.teoremas:
                self.saidas.append(f"{c.nome} = Prova verificada")
                return
            raise ErroOmega(f"Nome não declarado: {c.nome}")

        if c.tipo in ("provar", "teorema"):
            if c.expressao is None or c.direita is None:
                raise ErroOmega("Igualdade incompleta")
            if self.tensores or usa_tensor(c.expressao) or usa_tensor(c.direita):
                va = conferir_limites(expandir(c.expressao, self.tensores))
                vb = conferir_limites(expandir(c.direita, self.tensores))
                if formato(va) != formato(vb):
                    raise ErroOmega('Identidade tensorial falsa: dimensões diferentes')
                def canon(v):
                    if isinstance(v, tuple):
                        return [canon(x) for x in v]
                    return normalizar(v).forma_normal()
                if canon(va) != canon(vb):
                    raise ErroOmega('Identidade tensorial falsa; formas normais diferem')
                cert = {'tipo': 'identidade_tensorial',
                        'esquerda': expressao_para_dict(c.expressao),
                        'direita': expressao_para_dict(c.direita),
                        'definicoes': {k: expressao_para_dict(v) for k, v in self.tensores.items()},
                        'dimensoes': list(formato(va)), 'formas': canon(va)}
                if c.tipo == 'teorema':
                    cert['nome'] = c.nome
                self.guardar(cert)
                if c.tipo == 'teorema':
                    self.teoremas[c.nome] = cert
                    self.saidas.append(f'TEOREMA {c.nome}: identidade tensorial demonstrada')
                else:
                    self.saidas.append('PROVADO: identidade tensorial exata')
                return
            a, b = normalizar(c.expressao), normalizar(c.direita)
            if a != b:
                raise ErroOmega("Identidade polinomial falsa; as formas normais diferem")
            cert = {"tipo": "identidade", "esquerda": expressao_para_dict(c.expressao),
                    "direita": expressao_para_dict(c.direita),
                    "forma_normal": a.forma_normal()}
            if c.tipo == "teorema":
                cert["nome"] = c.nome
            self.guardar(cert)
            if c.tipo == "teorema":
                self.teoremas[c.nome] = cert
                self.saidas.append(f"TEOREMA {c.nome}: demonstrado por identidade polinomial")
            else:
                self.saidas.append("PROVADO: identidade polinomial exata")
            return

        if c.tipo == "verificar":
            cert = self.teoremas.get(c.nome)
            if cert is None or not verificar_certificado(cert):
                raise ErroOmega(f"Teorema {c.nome!r} não declarado ou prova inválida")
            self.saidas.append(f"VERIFICADO: teorema {c.nome}")
            return

        if c.tipo == "reescrever":
            antiga, p = self.perda(c.nome)
            if c.expressao is None:
                raise ErroOmega("Nova expressão não fornecida")
            v = self.expansao_com_prova(c.expressao) if self.tensores else expandir(c.expressao,{})
            if formato(v):
                raise ErroOmega('Reescrita de perda precisa ser escalar')
            nova = para_ast(v)
            q = self.validar_variaveis(nova)
            if p != q:
                raise ErroOmega("Reescrita rejeitada: as expressões não são equivalentes")
            self.guardar({"tipo": "reescrita", "esquerda": expressao_para_dict(antiga),
                          "direita": expressao_para_dict(nova),
                          "forma_normal": p.forma_normal()})
            self.perdas[c.nome] = nova
            self.perdas_originais[c.nome] = c.expressao
            self.saidas.append(f"reescrita de {c.nome}: equivalência PROVADA")
            return

        if c.tipo in ("gradiente", "passo"):
            expr, p = self.perda(c.nome)
            if c.parametro in self.parametros_tensoriais:
                mapa = self.parametros_tensoriais[c.parametro]
                grads = retropropagar_tensores(self.perdas_originais.get(c.nome, expr),
                                                self.tensores, self.parametros)
                resultado = como_listas(remodelar(mapa, grads))
                antes = dict(self.parametros)
                if c.tipo == 'gradiente':
                    self.guardar({'tipo': 'gradiente_tensor',
                                  'expressao': expressao_para_dict(expr),
                                  'coordenadas': como_listas(mapa),
                                  'estado': serializar_estado(antes),
                                  'resultado': resultado})
                    self.saidas.append(f'd({c.nome})/d({c.parametro}) [tensor] = {resultado}')
                    return
                if c.taxa is None:
                    raise ErroOmega('Taxa ausente')
                taxa_exp = self.expansao_com_prova(c.taxa) if self.tensores or usa_tensor(c.taxa) else expandir(c.taxa,{})
                if formato(taxa_exp):
                    raise ErroOmega('Taxa deve ser escalar')
                tx_ast = para_ast(taxa_exp)
                taxa = self.validar_variaveis(tx_ast).avaliar(antes)
                if taxa <= 0:
                    raise ErroOmega('Taxa deve ser positiva')
                depois = dict(antes)
                for nome in folhas(mapa):
                    depois[nome] = antes[nome] - taxa * grads[nome]
                antiga, nova = p.avaliar(antes), p.avaliar(depois)
                if nova > antiga:
                    raise ErroOmega(f'Passo rejeitado: perda aumentaria de {antiga} para {nova}')
                self.guardar({'tipo': 'passo_tensor',
                              'expressao': expressao_para_dict(expr),
                              'expressao_taxa': expressao_para_dict(tx_ast),
                              'coordenadas': como_listas(mapa),
                              'estado_antes': serializar_estado(antes),
                              'estado_depois': serializar_estado(depois),
                              'gradientes': resultado, 'taxa': str(taxa),
                              'perda_antes': str(antiga), 'perda_depois': str(nova)})
                self.parametros = depois
                self.saidas.append(f'passo ACEITO: {c.parametro} '
                                   f'{como_listas(remodelar(mapa, antes))} -> '
                                   f'{como_listas(remodelar(mapa, depois))}; '
                                   f'{c.nome} {antiga} -> {nova}')
                return
            if c.parametro not in self.parametros:
                raise ErroOmega(f"Parâmetro não declarado: {c.parametro}")
            grad = p.derivar(c.parametro).avaliar(self.parametros)
            if c.tipo == "gradiente":
                self.guardar({"tipo": "gradiente", "expressao": expressao_para_dict(expr),
                              "parametro": c.parametro,
                              "estado": serializar_estado(self.parametros),
                              "resultado": str(grad)})
                self.saidas.append(f"d({c.nome})/d({c.parametro}) = {grad}")
                return
            if c.taxa is None:
                raise ErroOmega("Taxa de aprendizado ausente")
            tx = self.expansao_com_prova(c.taxa) if self.tensores or usa_tensor(c.taxa) else expandir(c.taxa, {})
            if formato(tx):
                raise ErroOmega('Taxa deve ser escalar')
            taxa_expr = para_ast(tx)
            taxa = self.validar_variaveis(taxa_expr).avaliar(self.parametros)
            if taxa <= 0:
                raise ErroOmega("Taxa deve ser positiva")
            antes = dict(self.parametros)
            old = p.avaliar(antes)
            novo_estado = dict(antes)
            novo_estado[c.parametro] = antes[c.parametro] - taxa * grad
            new = p.avaliar(novo_estado)
            if new > old:
                raise ErroOmega(f"Passo rejeitado: perda aumentaria de {old} para {new}")
            self.guardar({"tipo": "passo", "expressao": expressao_para_dict(expr),
                          "expressao_taxa": expressao_para_dict(taxa_expr),
                          "parametro": c.parametro,
                          "estado_antes": serializar_estado(antes),
                          "estado_depois": serializar_estado(novo_estado),
                          "taxa": str(taxa), "gradiente": str(grad),
                          "perda_antes": str(old), "perda_depois": str(new)})
            self.parametros = novo_estado
            self.saidas.append(
                f"passo ACEITO: {c.parametro} {antes[c.parametro]} -> "
                f"{novo_estado[c.parametro]}; {c.nome} {old} -> {new}")
            return
        raise ErroOmega(f"Tipo de comando desconhecido: {c.tipo}")
