"""Verificação independente de certificados de gradiente e passo tensorial.

Não importa executor, diferenciação automática ou biblioteca polinomial
produtora. O núcleo omega.nucleo recalcula derivadas algébricas exatamente.
"""
from __future__ import annotations

from fractions import Fraction
from . import nucleo as n


def estrutura(coordenadas, valores):
    """Valida duas árvores isomorfas e devolve pares (coordenada, valor)."""
    if not isinstance(coordenadas, list) or not 1 <= len(coordenadas) <= 32:
        raise n.ProvaInvalida('Estrutura de coordenadas inválida')
    if not isinstance(valores, list) or len(coordenadas) != len(valores):
        raise n.ProvaInvalida('Formato de resultados incompatível')
    if all(isinstance(x, str) for x in coordenadas):
        if not all(isinstance(v, str) for v in valores):
            raise n.ProvaInvalida('Valores do vetor devem ser racionais textuais')
        return list(zip(coordenadas, valores))
    if not all(isinstance(x, list) for x in coordenadas):
        raise n.ProvaInvalida('Matriz tensorial irregular')
    tamanho = len(coordenadas[0])
    if not 1 <= tamanho <= 32 or any(len(linha) != tamanho for linha in coordenadas):
        raise n.ProvaInvalida('Matriz tensorial não retangular')
    saida = []
    for xs, ys in zip(coordenadas, valores):
        if not isinstance(ys, list):
            raise n.ProvaInvalida('Gradiente matricial inválido')
        pares = estrutura(xs, ys)
        saida.extend(pares)
    return saida


def checar_nomes(pares, estado):
    nomes = [nome for nome, _ in pares]
    if (len(nomes) != len(set(nomes)) or
            any(not isinstance(x, str) or not x.startswith('__omega_coord_') or
                not x.isidentifier() or x not in estado for x in nomes)):
        raise n.ProvaInvalida('Coordenadas não pertencem ao estado ou repetidas')


def validar_gradiente_tensor(cert):
    p = n.polinomio(cert['expressao'])
    estado = n.ler_estado(cert['estado'])
    pares = estrutura(cert['coordenadas'], cert['resultado'])
    checar_nomes(pares, estado)
    return all(valor == str(n.avaliar(n.derivada(p, nome), estado)) for nome, valor in pares)


def validar_passo_tensor(cert):
    p = n.polinomio(cert['expressao'])
    t = n.polinomio(cert['expressao_taxa'])
    antes, depois = n.ler_estado(cert['estado_antes']), n.ler_estado(cert['estado_depois'])
    if set(antes) != set(depois):
        return False
    pares = estrutura(cert['coordenadas'], cert['gradientes'])
    checar_nomes(pares, antes)
    taxa = n.avaliar(t, antes)
    if taxa <= 0 or cert['taxa'] != str(taxa):
        return False
    calculado = dict(antes)
    for nome, grad_string in pares:
        grad = n.avaliar(n.derivada(p, nome), antes)
        if grad_string != str(grad):
            return False
        calculado[nome] = antes[nome] - taxa * grad
    if calculado != depois:
        return False
    perda_antes, perda_depois = n.avaliar(p, antes), n.avaliar(p, depois)
    return (perda_depois <= perda_antes and
            cert['perda_antes'] == str(perda_antes) and
            cert['perda_depois'] == str(perda_depois))
